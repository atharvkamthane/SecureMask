"""OCR engine: Google Cloud Vision primary → PaddleOCR fallback 1 → EasyOCR fallback 2.

Key improvements over v1:
  - Google Vision client is cached (one-time init) — fixes the "never calls API" bug
  - All engines receive the *preprocessed* image, not the raw upload
  - Permanent disable only on billing/credential errors; transient errors retry
  - Hindi PaddleOCR is only invoked when English confidence is below threshold
  - EasyOCR uses the enhanced-contrast image, not raw
  - save_preprocessed_variants() called once per scan to avoid repeated processing
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from statistics import mean

import cv2
import numpy as np
from PIL import Image

from securemask.config import GCP_CREDENTIALS_PATH, STORAGE_DIR
from securemask.models.detected_field import BoundingBox

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Thresholds / tunables
# ------------------------------------------------------------------

PADDLE_CONFIDENCE_THRESHOLD = 0.55
PADDLE_HINDI_CONFIDENCE_THRESHOLD = 0.50  # lower bar for supplementary Hindi pass
MIN_WORDS_THRESHOLD = 3
EASYOCR_FALLBACK_THRESHOLD = 0.45  # trigger EasyOCR if best result is below this

# Permanent-disable error substrings (billing/auth — no point retrying)
_PERMANENT_VISION_ERRORS = {
    "BILLING_DISABLED",
    "billing account",
    "403",
    "permission_denied",
    "SERVICE_DISABLED",
    "API_KEY_INVALID",
}

_google_vision_disabled = False          # True only on permanent errors
_google_vision_transient_errors = 0      # count of non-permanent errors
_VISION_TRANSIENT_LIMIT = 3             # give up after this many transient failures


@dataclass
class OCRWord:
    text: str
    confidence: float
    bbox: BoundingBox


@dataclass
class OCRResult:
    full_text: str
    words: list[OCRWord] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0

    @property
    def avg_confidence(self) -> float:
        if not self.words:
            return 0.0
        return mean(w.confidence for w in self.words)


# ------------------------------------------------------------------
# Google Cloud Vision — cached client + smart error handling
# ------------------------------------------------------------------

def _gcp_credentials_configured() -> bool:
    """Return True if GCP credentials are discoverable."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return Path(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]).exists()
    if GCP_CREDENTIALS_PATH.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_CREDENTIALS_PATH)
        logger.info("GCP credentials loaded from %s", GCP_CREDENTIALS_PATH)
        return True
    return False


@lru_cache(maxsize=1)
def _get_vision_client():
    """Lazy-init and **cache** the Vision client.

    The original code created a new client on every OCR call, which:
      1. Added ~200–500 ms cold-start overhead per document
      2. Silently failed if the first import raised an exception, then
         permanently marked Vision as disabled even on retry

    This function runs once per process lifetime.
    """
    try:
        from google.cloud import vision as gv
        client = gv.ImageAnnotatorClient()
        logger.info("Google Cloud Vision client initialised and cached")
        return client
    except Exception as exc:
        logger.warning("Could not initialise Vision client: %s", exc)
        return None


def _is_permanent_vision_error(message: str) -> bool:
    msg_lower = message.lower()
    return any(tag.lower() in msg_lower for tag in _PERMANENT_VISION_ERRORS)


def _google_vision_ocr(image_path: str) -> OCRResult | None:
    """Extract text via Google Cloud Vision API.

    Uses the cached client. Only permanently disables on billing/auth errors;
    transient network errors are counted and allowed up to _VISION_TRANSIENT_LIMIT.
    Sends the (preprocessed color) image for best accuracy.
    """
    global _google_vision_disabled, _google_vision_transient_errors

    if _google_vision_disabled:
        return None
    if _google_vision_transient_errors >= _VISION_TRANSIENT_LIMIT:
        logger.warning("Vision skipped: too many transient errors (%d)", _google_vision_transient_errors)
        return None
    if not _gcp_credentials_configured():
        logger.info("Google Vision credentials not found — skipping")
        return None

    client = _get_vision_client()
    if client is None:
        return None

    try:
        from google.cloud import vision as gv

        with open(image_path, "rb") as fh:
            content = fh.read()

        image_obj = gv.Image(content=content)
        # document_text_detection is better than text_detection for dense layouts
        response = client.document_text_detection(image=image_obj)

        if response.error.message:
            msg = response.error.message
            if _is_permanent_vision_error(msg):
                _google_vision_disabled = True
                logger.error("Vision permanently disabled: %s", msg)
            else:
                _google_vision_transient_errors += 1
                logger.warning("Vision transient error (%d/%d): %s",
                               _google_vision_transient_errors, _VISION_TRANSIENT_LIMIT, msg)
            return None

        # Reset transient counter on success
        _google_vision_transient_errors = 0

        img = cv2.imread(str(image_path))
        if img is None:
            img = np.array(Image.open(image_path).convert("RGB"))
        h, w = img.shape[:2]

        words: list[OCRWord] = []
        parts: list[str] = []

        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        text = "".join(s.text for s in word.symbols)
                        if not text.strip():
                            continue
                        conf = float(word.confidence) if word.confidence else 0.85
                        verts = word.bounding_box.vertices
                        xs = [v.x for v in verts]
                        ys = [v.y for v in verts]
                        bx, by = min(xs), min(ys)
                        bw, bh = max(xs) - bx, max(ys) - by
                        words.append(OCRWord(
                            text=text, confidence=conf,
                            bbox=BoundingBox(bx, by, bw, bh),
                        ))
                        parts.append(text)

        if not words:
            logger.warning("Vision returned zero words for %s", image_path)
            return None

        full_text = " ".join(parts)
        logger.info("Google Vision: %d words, avg_conf=%.2f", len(words),
                    mean(w.confidence for w in words))
        return OCRResult(full_text=full_text, words=words, image_width=w, image_height=h)

    except Exception as exc:
        msg = str(exc)
        if _is_permanent_vision_error(msg):
            _google_vision_disabled = True
            logger.error("Vision permanently disabled: %s", exc)
        else:
            _google_vision_transient_errors += 1
            logger.error("Vision transient exception (%d/%d): %s",
                         _google_vision_transient_errors, _VISION_TRANSIENT_LIMIT, exc)
        return None


# ------------------------------------------------------------------
# PaddleOCR — lazy cached readers
# ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_paddle_reader_en():
    try:
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        os.environ["FLAGS_use_mkldnn"] = "0"
        from paddleocr import PaddleOCR
        try:
            reader = PaddleOCR(lang="en", show_log=False)
        except Exception:
            reader = PaddleOCR(lang="en")
        logger.info("PaddleOCR (English) initialised")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR (en) unavailable: %s", exc)
        return None


@lru_cache(maxsize=1)
def _get_paddle_reader_hi():
    try:
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        os.environ["FLAGS_use_mkldnn"] = "0"
        from paddleocr import PaddleOCR
        try:
            reader = PaddleOCR(lang="hi", show_log=False)
        except Exception:
            reader = PaddleOCR(lang="hi")
        logger.info("PaddleOCR (Hindi) initialised")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR (hi) unavailable: %s", exc)
        return None


def _parse_paddle_result(result, image_path: str) -> OCRResult | None:
    """Parse PaddleOCR predict() result (supports both legacy and new API)."""
    if result is None:
        return None

    img = cv2.imread(str(image_path))
    if img is None:
        img = np.array(Image.open(image_path).convert("RGB"))
    h, w = img.shape[:2]

    words: list[OCRWord] = []
    parts: list[str] = []

    for res in result:
        # ---------- New PaddleOCR API (>= 2.8 / 3.x) ----------
        if hasattr(res, "rec_texts") and hasattr(res, "dt_polys"):
            texts = res.rec_texts or []
            scores = res.rec_scores or []
            polys = res.dt_polys or []
            for i, text in enumerate(texts):
                text = str(text).strip()
                if not text:
                    continue
                conf = float(scores[i]) if i < len(scores) else 0.5
                if i < len(polys):
                    poly = polys[i]
                    xs = [int(p[0]) for p in poly]
                    ys = [int(p[1]) for p in poly]
                    bx, by = int(min(xs)), int(min(ys))
                    bw, bh = int(max(xs) - bx), int(max(ys) - by)
                else:
                    bx, by, bw, bh = 0, 0, 1, 1
                words.append(OCRWord(text=text, confidence=conf,
                                     bbox=BoundingBox(bx, by, bw, bh)))
                parts.append(text)
            continue

        # ---------- Legacy PaddleOCR API (< 2.8) ----------
        if isinstance(res, list):
            for line in res:
                if not isinstance(line, (list, tuple)) or len(line) != 2:
                    continue
                try:
                    points, (text, conf) = line
                    text = str(text).strip()
                    if not text:
                        continue
                    xs = [int(p[0]) for p in points]
                    ys = [int(p[1]) for p in points]
                    bx, by = int(min(xs)), int(min(ys))
                    bw, bh = int(max(xs) - bx), int(max(ys) - by)
                    words.append(OCRWord(text=text, confidence=float(conf),
                                         bbox=BoundingBox(bx, by, bw, bh)))
                    parts.append(text)
                except Exception:
                    pass

    if not words:
        return None

    words.sort(key=lambda word: (word.bbox.y, word.bbox.x))
    return OCRResult(
        full_text=" ".join(parts),
        words=words,
        image_width=w,
        image_height=h,
    )


def _run_paddle(reader, image_path: str) -> OCRResult | None:
    """Run a single PaddleOCR reader and parse the result."""
    if reader is None:
        return None
    try:
        raw = reader.predict(str(image_path))
        return _parse_paddle_result(raw, image_path)
    except Exception as exc:
        logger.error("PaddleOCR predict() failed: %s", exc)
        return None


def _paddle_ocr(image_path: str, force_hindi: bool = False) -> OCRResult | None:
    """English PaddleOCR pass; Hindi pass only when english confidence is low.

    Speed optimisation: the original code always ran both languages.
    We now run Hindi only when English avg_confidence < PADDLE_HINDI_CONFIDENCE_THRESHOLD
    or when force_hindi=True (caller suspects Hindi content).
    """
    result_en = _run_paddle(_get_paddle_reader_en(), image_path)
    en_conf = result_en.avg_confidence if result_en else 0.0

    run_hindi = force_hindi or en_conf < PADDLE_HINDI_CONFIDENCE_THRESHOLD
    result_hi = _run_paddle(_get_paddle_reader_hi(), image_path) if run_hindi else None

    # Merge: prefer English words; add non-overlapping Hindi words
    if result_en and result_hi:
        merged_words = list(result_en.words)
        for hw in result_hi.words:
            overlap = any(
                abs(hw.bbox.x - ew.bbox.x) < 20 and abs(hw.bbox.y - ew.bbox.y) < 20
                for ew in result_en.words
            )
            if not overlap:
                merged_words.append(hw)
        merged_words.sort(key=lambda word: (word.bbox.y, word.bbox.x))
        return OCRResult(
            full_text=" ".join(w.text for w in merged_words),
            words=merged_words,
            image_width=result_en.image_width,
            image_height=result_en.image_height,
        )

    return result_en or result_hi


# ------------------------------------------------------------------
# EasyOCR — secondary fallback
# ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_easyocr_reader():
    try:
        import easyocr
        model_dir = STORAGE_DIR / "easyocr"
        model_dir.mkdir(parents=True, exist_ok=True)
        # gpu=False keeps it cross-platform; verbose=False suppresses logs
        return easyocr.Reader(["en", "hi"], gpu=False, verbose=False,
                              model_storage_directory=str(model_dir))
    except Exception as exc:
        logger.warning("EasyOCR unavailable: %s", exc)
        return None


def _split_easyocr_phrases(words: list[OCRWord]) -> list[OCRWord]:
    """Split multi-word EasyOCR phrase tokens into individual sub-word tokens.

    EasyOCR often returns entire lines as a single token (e.g.
    'जन्म तारीख DOB: 15 04 2006' as one OCRWord). This makes per-field
    bounding boxes unreliable. We split on whitespace and interpolate
    sub-word bboxes proportionally by character count across the parent box.
    """
    result: list[OCRWord] = []
    for word in words:
        sub_tokens = word.text.split()
        if len(sub_tokens) <= 1:
            result.append(word)
            continue

        # Interpolate bbox horizontally by character count
        total_chars = max(sum(len(t) for t in sub_tokens), 1)
        parent_x = word.bbox.x
        parent_w = word.bbox.width
        parent_y = word.bbox.y
        parent_h = word.bbox.height

        x_cursor = parent_x
        for token in sub_tokens:
            token_chars = max(len(token), 1)
            token_w = int(parent_w * token_chars / total_chars)
            result.append(OCRWord(
                text=token,
                confidence=word.confidence,
                bbox=BoundingBox(
                    int(x_cursor), int(parent_y),
                    int(token_w), int(parent_h),
                ),
            ))
            x_cursor += token_w

    return result


def _easyocr_fallback(image_path: str) -> OCRResult | None:
    reader = _get_easyocr_reader()
    if reader is None:
        return None
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            img = np.array(Image.open(image_path).convert("RGB"))
        h, w = img.shape[:2]

        results = reader.readtext(
            img, detail=1, paragraph=False,
            text_threshold=0.5, low_text=0.3, width_ths=0.7,
        )
        words: list[OCRWord] = []
        parts: list[str] = []
        for pts, text, conf in results:
            text = str(text).strip()
            if not text:
                continue
            xs = [int(p[0]) for p in pts]
            ys = [int(p[1]) for p in pts]
            bx, by = int(min(xs)), int(min(ys))
            bw, bh = int(max(xs) - bx), int(max(ys) - by)
            words.append(OCRWord(
                text=text, confidence=float(conf),
                bbox=BoundingBox(bx, by, bw, bh),
            ))
            parts.append(text)

        if not words:
            return None

        # Split merged phrase tokens into individual sub-words with interpolated bboxes
        words = _split_easyocr_phrases(words)

        return OCRResult(full_text=" ".join(w.text for w in words), words=words,
                         image_width=int(w), image_height=int(h))
    except Exception as exc:
        logger.error("EasyOCR failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Preprocessed-image temp-file helper
# ------------------------------------------------------------------

def _write_temp_image(arr: np.ndarray, suffix: str = ".png") -> str:
    """Write a numpy array to a temp file and return its path.

    Used to pass preprocessed images to OCR engines that only accept file paths.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    cv2.imwrite(path, arr)
    return path


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

class OCREngine:
    """Multi-engine OCR with preprocessed routing.

    Google Vision  →  PaddleOCR (en, +hi if needed)  →  EasyOCR

    Each engine now receives the correct image variant:
      - Vision: deskewed JPEG color image (best for cloud model)
      - Paddle: sharpened grayscale (avoids double binarization)
      - EasyOCR: CLAHE-enhanced BGR (its own contrast logic)
    """

    def extract(
        self,
        image_path: str | Path,
        preprocessed_color_path: str | Path | None = None,
        preprocessed_gray_path: str | Path | None = None,
    ) -> OCRResult:
        """Run OCR with cascading fallback.

        Args:
            image_path: original uploaded file (used if preprocessed paths not given)
            preprocessed_color_path: path to save_preprocessed_variants()['color']
            preprocessed_gray_path:  path to save_preprocessed_variants()['enhanced_gray']

        Returns:
            Best OCRResult available.
        """
        raw_path = str(image_path)

        # Resolve which image path to hand each engine
        vision_path = str(preprocessed_color_path) if preprocessed_color_path else raw_path
        paddle_path = str(preprocessed_gray_path)  if preprocessed_gray_path  else raw_path
        easyocr_path = str(preprocessed_gray_path) if preprocessed_gray_path  else raw_path

        selected_result = None

        # ---- 1. Google Cloud Vision (primary) ----
        vision_result = _google_vision_ocr(vision_path)
        if vision_result and len(vision_result.words) >= MIN_WORDS_THRESHOLD:
            logger.info("OCR engine: Google Vision — %d words @ conf %.2f",
                        len(vision_result.words), vision_result.avg_confidence)
            selected_result = vision_result
        else:
            logger.info("Google Vision skipped/failed — trying PaddleOCR")

            # ---- 2. PaddleOCR (fallback 1) ----
            paddle_result = _paddle_ocr(paddle_path)
            if (paddle_result
                    and paddle_result.avg_confidence >= PADDLE_CONFIDENCE_THRESHOLD
                    and len(paddle_result.words) >= MIN_WORDS_THRESHOLD):
                logger.info("OCR engine: PaddleOCR — %d words @ conf %.2f",
                            len(paddle_result.words), paddle_result.avg_confidence)
                selected_result = paddle_result
            else:
                low_conf = paddle_result.avg_confidence if paddle_result else 0.0
                low_words = len(paddle_result.words) if paddle_result else 0
                logger.info("PaddleOCR below threshold (conf=%.2f, words=%d) — trying EasyOCR",
                            low_conf, low_words)

                # ---- 3. EasyOCR (fallback 2) ----
                easy_result = _easyocr_fallback(easyocr_path)
                if easy_result and easy_result.words:
                    logger.info("OCR engine: EasyOCR — %d words @ conf %.2f",
                                len(easy_result.words), easy_result.avg_confidence)
                    selected_result = easy_result
                else:
                    # ---- Best-effort: return whatever we have ----
                    for candidate in (vision_result, paddle_result, easy_result):
                        if candidate and candidate.words:
                            logger.warning("OCR: returning partial result from best-effort fallback")
                            selected_result = candidate
                            break

        if selected_result is None:
            logger.error("All OCR engines failed for %s", image_path)
            return OCRResult(full_text="", words=[], image_width=0, image_height=0)

        # Translate Devanagari digits U+0966 to U+096F to '0'-'9'
        devanagari_map = {
            '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
            '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
        }
        
        def normalize_text(text: str) -> str:
            if not text:
                return text
            return "".join(devanagari_map.get(char, char) for char in text)

        selected_result.full_text = normalize_text(selected_result.full_text)
        for w in selected_result.words:
            w.text = normalize_text(w.text)

        return selected_result