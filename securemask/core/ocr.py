"""OCR engine: PaddleOCR primary → Google Cloud Vision fallback.

PaddleOCR runs first. If average word confidence < 0.72 or < 5 words
detected, falls back to Google Vision DOCUMENT_TEXT_DETECTION (if GCP
credentials are available).
"""
from __future__ import annotations

import logging
import os
import re
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

PADDLE_CONFIDENCE_THRESHOLD = 0.55
MIN_WORDS_THRESHOLD = 3
_google_vision_disabled = False
_paddle_english_disabled = False
_paddle_hindi_disabled = False


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


# ---------------------------------------------------------------------------
# PaddleOCR engine
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_paddle_reader():
    """Lazy-init PaddleOCR reader (cached). Uses multi-language for Indian docs."""
    try:
        import os
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        os.environ["FLAGS_use_mkldnn"] = "0"  # Disable oneDNN to prevent PIR conversion errors
        from paddleocr import PaddleOCR
        reader = PaddleOCR(lang="en")
        logger.info("PaddleOCR engine initialised (English)")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR unavailable: %s", exc)
        return None


@lru_cache(maxsize=1)
def _get_paddle_reader_hi():
    """Lazy-init PaddleOCR Hindi reader for bilingual Indian documents."""
    try:
        import os
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        os.environ["FLAGS_use_mkldnn"] = "0"
        from paddleocr import PaddleOCR
        reader = PaddleOCR(lang="hi")
        logger.info("PaddleOCR engine initialised (Hindi)")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR Hindi unavailable: %s", exc)
        return None


def _parse_paddle_result(result, image_path: str) -> OCRResult | None:
    """Parse PaddleOCR predict() result into OCRResult."""
    if result is None:
        return None

    img = cv2.imread(str(image_path))
    if img is None:
        img = np.array(Image.open(image_path).convert("RGB"))
    h, w = img.shape[:2]

    words: list[OCRWord] = []
    parts: list[str] = []

    # New PaddleOCR predict() returns a list of result objects
    for res in result:
        if not hasattr(res, 'rec_texts') or not hasattr(res, 'dt_polys'):
            # Try legacy format: list of (points, (text, conf))
            try:
                if isinstance(res, list):
                    for line in res:
                        if isinstance(line, (list, tuple)) and len(line) == 2:
                            points, (text, conf) = line
                            text = str(text).strip()
                            if not text:
                                continue
                            xs = [int(p[0]) for p in points]
                            ys = [int(p[1]) for p in points]
                            bx, by = min(xs), min(ys)
                            bw, bh = max(xs) - bx, max(ys) - by
                            words.append(OCRWord(text=text, confidence=float(conf),
                                                 bbox=BoundingBox(bx, by, bw, bh)))
                            parts.append(text)
            except Exception:
                pass
            continue

        # New API: result has rec_texts, rec_scores, dt_polys
        texts = res.rec_texts if hasattr(res, 'rec_texts') else []
        scores = res.rec_scores if hasattr(res, 'rec_scores') else []
        polys = res.dt_polys if hasattr(res, 'dt_polys') else []

        for i, text in enumerate(texts):
            text = str(text).strip()
            if not text:
                continue
            conf = float(scores[i]) if i < len(scores) else 0.5
            if i < len(polys):
                poly = polys[i]
                xs = [int(p[0]) for p in poly]
                ys = [int(p[1]) for p in poly]
                bx, by = min(xs), min(ys)
                bw, bh = max(xs) - bx, max(ys) - by
            else:
                bx, by, bw, bh = 0, 0, 1, 1

            words.append(OCRWord(text=text, confidence=conf,
                                 bbox=BoundingBox(bx, by, bw, bh)))
            parts.append(text)

    if not words:
        return None

    full_text = " ".join(parts)
    return OCRResult(full_text=full_text, words=words, image_width=w, image_height=h)


def _paddle_ocr(image_path: str) -> OCRResult | None:
    """Extract text using PaddleOCR with English + Hindi multi-pass."""
    global _paddle_english_disabled, _paddle_hindi_disabled

    # --- English pass ---
    reader_en = None if _paddle_english_disabled else _get_paddle_reader()
    result_en = None
    if reader_en:
        try:
            raw = reader_en.predict(str(image_path))
            result_en = _parse_paddle_result(raw, image_path)
        except Exception as exc:
            _paddle_english_disabled = True
            logger.error("PaddleOCR (en) failed: %s", exc)

    # --- Hindi pass ---
    reader_hi = None if _paddle_hindi_disabled else _get_paddle_reader_hi()
    result_hi = None
    if reader_hi:
        try:
            raw = reader_hi.predict(str(image_path))
            result_hi = _parse_paddle_result(raw, image_path)
        except Exception as exc:
            _paddle_hindi_disabled = True
            logger.error("PaddleOCR (hi) failed: %s", exc)

    # --- Merge: pick the result with more words, then merge unique words from the other ---
    if result_en and result_hi:
        primary = result_en if len(result_en.words) >= len(result_hi.words) else result_hi
        secondary = result_hi if primary is result_en else result_en
        # Add unique words from secondary (based on bbox proximity)
        merged_words = list(primary.words)
        for sw in secondary.words:
            # Check if a similar word already exists at a similar position
            duplicate = False
            for pw in primary.words:
                if (abs(sw.bbox.x - pw.bbox.x) < 20 and
                    abs(sw.bbox.y - pw.bbox.y) < 20):
                    duplicate = True
                    break
            if not duplicate:
                merged_words.append(sw)
        merged_words.sort(key=lambda w: (w.bbox.y, w.bbox.x))
        full_text = " ".join(w.text for w in merged_words)
        return OCRResult(full_text=full_text, words=merged_words,
                         image_width=primary.image_width, image_height=primary.image_height)
    elif result_en:
        return result_en
    elif result_hi:
        return result_hi
    return None


# ---------------------------------------------------------------------------
# Google Cloud Vision fallback
# ---------------------------------------------------------------------------

def _google_vision_available() -> bool:
    """Check whether GCP Vision credentials are set up."""
    if _google_vision_disabled:
        return False
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    if GCP_CREDENTIALS_PATH.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_CREDENTIALS_PATH)
        return True
    return False


def _google_vision_ocr(image_path: str) -> OCRResult | None:
    """Extract text using Google Cloud Vision API."""
    global _google_vision_disabled

    if not _google_vision_available():
        return None

    try:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as fh:
            content = fh.read()

        image = vision.Image(content=content)
        response = client.document_text_detection(image=image)

        if response.error.message:
            logger.error("Google Vision error: %s", response.error.message)
            return None

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
                        conf = word.confidence
                        verts = word.bounding_box.vertices
                        xs = [v.x for v in verts]
                        ys = [v.y for v in verts]
                        bx = min(xs)
                        by = min(ys)
                        bw = max(xs) - bx
                        bh = max(ys) - by
                        words.append(OCRWord(
                            text=text,
                            confidence=float(conf),
                            bbox=BoundingBox(bx, by, bw, bh),
                        ))
                        parts.append(text)

        full_text = " ".join(parts) if parts else (response.full_text_annotation.text if response.full_text_annotation else "")
        return OCRResult(full_text=full_text, words=words, image_width=w, image_height=h)

    except Exception as exc:
        message = str(exc)
        if "BILLING_DISABLED" in message or "permission" in message.lower() or "403" in message:
            _google_vision_disabled = True
        logger.error("Google Vision OCR failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# EasyOCR secondary fallback
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_easyocr_reader():
    try:
        import easyocr
        model_dir = STORAGE_DIR / "easyocr"
        model_dir.mkdir(parents=True, exist_ok=True)
        return easyocr.Reader(["en", "hi"], gpu=False, verbose=False,
                              model_storage_directory=str(model_dir))
    except Exception:
        return None


def _easyocr_fallback(image_path: str) -> OCRResult | None:
    reader = _get_easyocr_reader()
    if reader is None:
        return None
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            img = np.array(Image.open(image_path).convert("RGB"))
        h, w = img.shape[:2]

        # Enhance contrast for better OCR on scanned documents
        enhanced = img.copy()
        if len(enhanced.shape) == 3:
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(l_channel)
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # Run EasyOCR with adjusted parameters for better detection
        results = reader.readtext(enhanced, detail=1,
                                  paragraph=False,
                                  text_threshold=0.5,
                                  low_text=0.3,
                                  width_ths=0.7)
        words: list[OCRWord] = []
        parts: list[str] = []
        for pts, text, conf in results:
            text = str(text).strip()
            if not text:
                continue
            xs = [int(p[0]) for p in pts]
            ys = [int(p[1]) for p in pts]
            bx, by = min(xs), min(ys)
            words.append(OCRWord(text=text, confidence=float(conf),
                                 bbox=BoundingBox(bx, by, max(xs) - bx, max(ys) - by)))
            parts.append(text)
        return OCRResult(full_text=" ".join(parts), words=words, image_width=w, image_height=h)
    except Exception as exc:
        logger.error("EasyOCR failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class OCREngine:
    """Multi-engine OCR: PaddleOCR → Google Vision → EasyOCR fallback chain."""

    def extract(self, image_path: str | Path) -> OCRResult:
        image_path = str(image_path)

        # Try PaddleOCR first
        result = _paddle_ocr(image_path)
        if result and result.avg_confidence >= PADDLE_CONFIDENCE_THRESHOLD and len(result.words) >= MIN_WORDS_THRESHOLD:
            logger.info("PaddleOCR: %d words, avg_conf=%.2f", len(result.words), result.avg_confidence)
            return result

        # Fallback 1: EasyOCR
        logger.info("PaddleOCR below threshold (%.2f/%d words), trying EasyOCR",
                     result.avg_confidence if result else 0, len(result.words) if result else 0)
        easy_result = _easyocr_fallback(image_path)
        if easy_result and easy_result.words:
            logger.info("EasyOCR: %d words, avg_conf=%.2f", len(easy_result.words), easy_result.avg_confidence)
            return easy_result

        # Fallback 2: Google Vision
        logger.info("EasyOCR unavailable/failed, trying Google Vision")
        vision_result = _google_vision_ocr(image_path)
        if vision_result and len(vision_result.words) >= MIN_WORDS_THRESHOLD:
            logger.info("Google Vision: %d words, avg_conf=%.2f", len(vision_result.words), vision_result.avg_confidence)
            return vision_result

        # Use whatever we have
        if result and result.words:
            return result
        if easy_result and easy_result.words:
            return easy_result
        if vision_result and vision_result.words:
            return vision_result

        logger.error("All OCR engines failed for %s", image_path)
        return OCRResult(full_text="", words=[], image_width=0, image_height=0)
