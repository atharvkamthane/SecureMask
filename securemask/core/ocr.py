"""OCR engine: PaddleOCR primary → EasyOCR fallback.

Root-cause fixes vs previous version:
  - PaddleOCR 3.x (PaddleX backend) returns dict-style result objects.
    The old parser used hasattr(res, 'rec_texts') which always failed on
    dict objects, causing 0 words every time. Fixed with a universal
    _extract_paddle_items() that tries dict-key → attr → legacy-list.
  - PaddleOCR 3.x's UVDoc/orientation sub-models require a COLOR BGR
    image. Passing enhanced_gray caused silent empty output.
    PaddleOCR now always receives the color image.
  - EasyOCR is now pre-warmed at module import so the first request
    doesn't pay a 5-10s cold-start penalty.
"""
from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from statistics import mean

# Must be set before any ``import paddle`` (Windows OneDNN / PIR crash).
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import cv2
import numpy as np
from PIL import Image

from securemask.config import STORAGE_DIR
from securemask.models.detected_field import BoundingBox

logger = logging.getLogger(__name__)

SKIP_EASYOCR_PREWARM_ENV = "SECUREMASK_SKIP_OCR_PREWARM"

# region agent log
def _agent_dbg_ocr(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    import json
    import time
    from pathlib import Path
    try:
        entry = {
            "sessionId": "edb17e",
            "runId": "post-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        log_path = Path(__file__).resolve().parents[2] / "debug-edb17e.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion

# ------------------------------------------------------------------
# Thresholds
# ------------------------------------------------------------------

PADDLE_CONFIDENCE_THRESHOLD = 0.40
PADDLE_HINDI_CONFIDENCE_THRESHOLD = 0.45
MIN_WORDS_THRESHOLD = 3


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
# PaddleOCR 3.x universal result extractor
# ------------------------------------------------------------------

def _box_from_points(poly) -> tuple[int, int, int, int]:
    """Return x, y, width, height from polygon or [x1,y1,x2,y2] box."""
    if not poly:
        return 0, 0, 1, 1
    flat = poly[0] if poly and isinstance(poly[0], (list, tuple)) and len(poly) == 1 else poly
    if len(flat) >= 4 and not isinstance(flat[0], (list, tuple)):
        x1, y1, x2, y2 = (float(flat[0]), float(flat[1]), float(flat[2]), float(flat[3]))
        return int(min(x1, x2)), int(min(y1, y2)), int(abs(x2 - x1)), int(abs(y2 - y1))
    xs = [int(p[0]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
    ys = [int(p[1]) for p in poly if isinstance(p, (list, tuple)) and len(p) >= 2]
    if not xs:
        return 0, 0, 1, 1
    bx, by = int(min(xs)), int(min(ys))
    return bx, by, int(max(xs) - bx), int(max(ys) - by)


def _extract_paddle_word_items(res) -> list[tuple[str, float, list]]:
    """Word-level tokens from PaddleOCR 3.5 ``text_word`` + ``text_word_boxes``."""
    def _get(obj, key, default=None):
        try:
            return obj[key]
        except (KeyError, TypeError, IndexError):
            pass
        try:
            return getattr(obj, key, default)
        except Exception:
            pass
        return default

    line_words = _get(res, "text_word")
    line_boxes = _get(res, "text_word_boxes")
    if not line_words or not line_boxes:
        return []

    line_scores = _get(res, "rec_scores") or []
    items: list[tuple[str, float, list]] = []
    for line_idx, (words, boxes) in enumerate(zip(line_words, line_boxes)):
        conf = float(line_scores[line_idx]) if line_idx < len(line_scores) else 0.75
        if not isinstance(words, (list, tuple)):
            continue
        box_list = boxes if isinstance(boxes, (list, tuple)) else []
        for word_idx, token in enumerate(words):
            text = str(token).strip()
            if not text:
                continue
            poly = list(box_list[word_idx]) if word_idx < len(box_list) else []
            items.append((text, conf, poly))
    return items


def _extract_paddle_items(res) -> list[tuple[str, float, list]]:
    """
    Extract (text, score, polygon_points) triples from a single PaddleOCR
    result item, handling every API variant we've seen in the wild:

      A) PaddleOCR 3.x / PaddleX  — dict-like access
            res['rec_texts'], res['rec_scores'], res['dt_polys']

      B) PaddleOCR 2.8 new-style   — attribute access
            res.rec_texts, res.rec_scores, res.dt_polys

      C) PaddleOCR < 2.8 legacy    — nested list
            [ ([pts], (text, conf)), ... ]
    """
    # ---------- helper: pull a value by key or attr ----------
    def _get(obj, key, default=None):
        try:
            return obj[key]
        except (KeyError, TypeError, IndexError):
            pass
        try:
            return getattr(obj, key, default)
        except Exception:
            pass
        return default

    # ---------- A / B: structured result ----------
    rec_texts = _get(res, "rec_texts")
    if rec_texts is not None:
        rec_scores = _get(res, "rec_scores") or []
        dt_polys   = _get(res, "dt_polys")   or []
        items = []
        for i, text in enumerate(rec_texts):
            text = str(text).strip()
            if not text:
                continue
            conf  = float(rec_scores[i]) if i < len(rec_scores) else 0.5
            poly  = list(dt_polys[i])    if i < len(dt_polys)   else []
            items.append((text, conf, poly))
        return items

    # ---------- C: legacy nested list ----------
    if isinstance(res, (list, tuple)):
        items = []
        for line in res:
            if not isinstance(line, (list, tuple)) or len(line) != 2:
                continue
            try:
                points, (text, conf) = line
                text = str(text).strip()
                if text:
                    items.append((text, float(conf), list(points)))
            except Exception:
                pass
        return items

    return []


def _parse_paddle_result(result, image_path: str) -> OCRResult | None:
    """Parse a PaddleOCR predict() result into OCRResult.

    `result` can be a generator, a list, or a single result object.
    Converts generators to list first so we can iterate safely.
    """
    if result is None:
        return None

    # Materialise generator (PaddleOCR 3.x returns a generator)
    if hasattr(result, "__next__") or hasattr(result, "__iter__") and not isinstance(result, (list, tuple)):
        try:
            result = list(result)
        except Exception as exc:
            logger.error("PaddleOCR: failed to materialise generator: %s", exc)
            return None

    img = cv2.imread(str(image_path))
    if img is None:
        img = np.array(Image.open(image_path).convert("RGB"))
    img_h, img_w = img.shape[:2]

    words: list[OCRWord] = []
    parts: list[str] = []

    for res in result:
        word_items = _extract_paddle_word_items(res)
        line_items = _extract_paddle_items(res) if not word_items else []
        for text, conf, poly in (word_items or line_items):
            bx, by, bw, bh = _box_from_points(poly)
            words.append(OCRWord(text=text, confidence=conf,
                                  bbox=BoundingBox(bx, by, bw, bh)))
            parts.append(text)

    if not words:
        # Log result structure to help debug future API changes
        try:
            sample = list(result)[:2] if result else []
            logger.warning(
                "PaddleOCR: 0 words extracted. result type=%s, sample=%s",
                type(result).__name__,
                [type(r).__name__ for r in sample],
            )
        except Exception:
            pass
        return None

    words.sort(key=lambda w: (w.bbox.y, w.bbox.x))
    return OCRResult(
        full_text=" ".join(parts),
        words=words,
        image_width=int(img_w),
        image_height=int(img_h),
    )


# ------------------------------------------------------------------
# PaddleOCR lazy cached readers
# ------------------------------------------------------------------

def _paddle_env_setup() -> None:
    """Disable OneDNN/MKLDNN — required on Windows+Paddle 3.3+ to avoid PIR crash."""
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["FLAGS_use_mkldnn"] = "0"
    os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"


def _create_paddle_reader(lang: str):
    """PaddleOCR 3.5+ init (no show_log; enable_mkldnn=False avoids OneDNN crash)."""
    _paddle_env_setup()
    from paddleocr import PaddleOCR
    return PaddleOCR(
        lang=lang,
        enable_mkldnn=False,
        return_word_box=True,
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
    )


@lru_cache(maxsize=1)
def _get_paddle_reader_en():
    try:
        reader = _create_paddle_reader("en")
        logger.info("PaddleOCR (English) initialised")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR (en) unavailable: %s", exc)
        return None


@lru_cache(maxsize=1)
def _get_paddle_reader_hi():
    try:
        reader = _create_paddle_reader("hi")
        logger.info("PaddleOCR (Hindi) initialised")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR (hi) unavailable: %s", exc)
        return None


def _run_paddle(reader, image_path: str) -> OCRResult | None:
    if reader is None:
        return None
    try:
        raw = reader.predict(str(image_path))
        return _parse_paddle_result(raw, image_path)
    except Exception as exc:
        logger.error("PaddleOCR predict() failed: %s", exc)
        # region agent log
        _agent_dbg_ocr(
            "ocr.py:_run_paddle",
            "paddle_predict_failed",
            {"error": str(exc)[:200], "image": str(image_path)[-80:]},
            "H7",
        )
        # endregion
        return None


def _paddle_ocr(image_path: str, force_hindi: bool = False) -> OCRResult | None:
    """Run English PaddleOCR; Hindi only when English confidence is low.

    IMPORTANT: image_path must point to a COLOR (BGR/RGB) image.
    PaddleOCR 3.x's UVDoc document-unwarping and orientation-detection
    sub-models require color input — grayscale produces silent empty output.
    """
    result_en = _run_paddle(_get_paddle_reader_en(), image_path)
    en_conf   = result_en.avg_confidence if result_en else 0.0

    run_hindi = force_hindi or en_conf < PADDLE_HINDI_CONFIDENCE_THRESHOLD
    result_hi = _run_paddle(_get_paddle_reader_hi(), image_path) if run_hindi else None

    if result_en and result_hi:
        merged = list(result_en.words)
        for hw in result_hi.words:
            overlap = any(
                abs(hw.bbox.x - ew.bbox.x) < 20 and abs(hw.bbox.y - ew.bbox.y) < 20
                for ew in result_en.words
            )
            if not overlap:
                merged.append(hw)
        merged.sort(key=lambda w: (w.bbox.y, w.bbox.x))
        return OCRResult(
            full_text=" ".join(w.text for w in merged),
            words=merged,
            image_width=result_en.image_width,
            image_height=result_en.image_height,
        )

    return result_en or result_hi


# ------------------------------------------------------------------
# EasyOCR — fallback engine (pre-warmed at import)
# ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_easyocr_reader():
    try:
        import easyocr
        model_dir = STORAGE_DIR / "easyocr"
        model_dir.mkdir(parents=True, exist_ok=True)
        reader = easyocr.Reader(["en", "hi"], gpu=False, verbose=False,
                                model_storage_directory=str(model_dir))
        logger.info("EasyOCR reader initialised (en+hi)")
        return reader
    except Exception as exc:
        logger.warning("EasyOCR unavailable: %s", exc)
        return None


def _prewarm_easyocr() -> None:
    """Call once at startup so the first real request doesn't pay cold-start.

    Runs in a background thread to avoid blocking uvicorn startup.
    """
    import threading
    def _warm():
        try:
            _get_easyocr_reader()
        except Exception:
            pass
    threading.Thread(target=_warm, daemon=True, name="easyocr-prewarm").start()


def _prewarm_paddle() -> None:
    """Pre-load English PaddleOCR at startup (logs success or WARNING)."""
    import threading

    def _warm():
        try:
            reader = _get_paddle_reader_en()
            if reader is None:
                logger.warning(
                    "PaddleOCR (English) pre-warm failed: reader is None "
                    "(check earlier WARNING for exception)"
                )
        except Exception as exc:
            logger.warning("PaddleOCR (English) pre-warm failed: %s", exc)

    threading.Thread(target=_warm, daemon=True, name="paddle-prewarm").start()


def _split_easyocr_phrases(words: list[OCRWord]) -> list[OCRWord]:
    """Split multi-word EasyOCR phrase tokens into individual sub-word tokens.

    EasyOCR often returns entire lines as one token. We split on whitespace
    and interpolate sub-word bboxes proportionally by character count.
    """
    result: list[OCRWord] = []
    for word in words:
        sub_tokens = word.text.split()
        if len(sub_tokens) <= 1:
            result.append(word)
            continue
        total_chars = max(sum(len(t) for t in sub_tokens), 1)
        x_cursor = word.bbox.x
        for token in sub_tokens:
            token_w = int(word.bbox.width * len(token) / total_chars)
            result.append(OCRWord(
                text=token,
                confidence=word.confidence,
                bbox=BoundingBox(int(x_cursor), int(word.bbox.y),
                                 int(token_w), int(word.bbox.height)),
            ))
            x_cursor += token_w
    return result


def _easyocr_fallback(image_path: str) -> OCRResult | None:
    """EasyOCR on a COLOR image (best accuracy)."""
    reader = _get_easyocr_reader()
    if reader is None:
        return None
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            img = np.array(Image.open(image_path).convert("RGB"))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        img_h, img_w = img.shape[:2]

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
            words.append(OCRWord(
                text=text, confidence=float(conf),
                bbox=BoundingBox(bx, by, int(max(xs) - bx), int(max(ys) - by)),
            ))
            parts.append(text)

        if not words:
            return None

        words = _split_easyocr_phrases(words)
        return OCRResult(full_text=" ".join(w.text for w in words),
                         words=words, image_width=int(img_w), image_height=int(img_h))
    except Exception as exc:
        logger.error("EasyOCR failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Devanagari digit normalizer
# ------------------------------------------------------------------

_DEVA_MAP = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
}


def _normalize(text: str) -> str:
    return "".join(_DEVA_MAP.get(c, c) for c in text) if text else text


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

# Pre-warm EasyOCR in background when module loads so first real
# request doesn't incur cold-start latency.
#
# Tests and one-off scripts can opt out by setting
# SECUREMASK_SKIP_OCR_PREWARM=1 before importing this module.
if os.getenv(SKIP_EASYOCR_PREWARM_ENV) != "1":
    _prewarm_easyocr()
    _prewarm_paddle()


class OCREngine:
    """PaddleOCR (primary) → EasyOCR (fallback).

    Image routing — CRITICAL for PaddleOCR 3.x:
      PaddleOCR receives the COLOR image (save_preprocessed_variants()['color']).
      Passing grayscale to PaddleOCR 3.x causes its UVDoc / orientation
      sub-models to return empty output silently.

      EasyOCR also receives the color image (its own contrast pipeline
      works best on color).
    """

    def extract(
        self,
        image_path: str | Path,
        preprocessed_color_path: str | Path | None = None,
        preprocessed_gray_path: str | Path | None = None,
    ) -> OCRResult:
        raw_path = str(image_path)

        # Both engines get the COLOR image — see class docstring for why
        color_path = str(preprocessed_color_path) if preprocessed_color_path else raw_path

        # ---- 1. PaddleOCR ----
        paddle_result = _paddle_ocr(color_path)
        paddle_ok = (
            paddle_result is not None
            and len(paddle_result.words) >= MIN_WORDS_THRESHOLD
        )

        # ---- 2. EasyOCR (word-level boxes; also fallback when Paddle fails) ----
        easy_result = _easyocr_fallback(color_path)

        if paddle_ok:
            final = paddle_result
            engine = "paddle"
            if easy_result and len(easy_result.words) > len(paddle_result.words):
                final = OCRResult(
                    full_text=paddle_result.full_text or easy_result.full_text,
                    words=easy_result.words,
                    image_width=paddle_result.image_width or easy_result.image_width,
                    image_height=paddle_result.image_height or easy_result.image_height,
                )
                engine = "paddle_text+easyocr_boxes"
            logger.info(
                "OCR engine: %s — %d words @ conf %.2f",
                engine, len(final.words), final.avg_confidence,
            )
            # region agent log
            _agent_dbg_ocr(
                "ocr.py:extract",
                "engine_selected",
                {
                    "engine": engine,
                    "words": len(final.words),
                    "conf": round(final.avg_confidence, 3),
                    "preview": final.full_text[:200],
                },
                "H7",
            )
            # endregion
            return self._finalize(final)

        low_conf  = paddle_result.avg_confidence if paddle_result else 0.0
        low_words = len(paddle_result.words)      if paddle_result else 0
        logger.info("PaddleOCR unavailable (conf=%.2f, words=%d) — using EasyOCR",
                    low_conf, low_words)
        # region agent log
        _agent_dbg_ocr(
            "ocr.py:extract",
            "paddle_skipped",
            {"conf": round(low_conf, 3), "words": low_words},
            "H7",
        )
        # endregion

        if easy_result and easy_result.words:
            logger.info("OCR engine: EasyOCR — %d words @ conf %.2f",
                        len(easy_result.words), easy_result.avg_confidence)
            # region agent log
            _agent_dbg_ocr(
                "ocr.py:extract",
                "engine_selected",
                {
                    "engine": "easyocr",
                    "words": len(easy_result.words),
                    "conf": round(easy_result.avg_confidence, 3),
                    "preview": easy_result.full_text[:200],
                },
                "H7",
            )
            # endregion
            return self._finalize(easy_result)

        # Best-effort
        for candidate in (paddle_result, easy_result):
            if candidate and candidate.words:
                logger.warning("OCR: returning partial result as best-effort")
                return self._finalize(candidate)

        logger.error("All OCR engines failed for %s", image_path)
        return OCRResult(full_text="", words=[], image_width=0, image_height=0)

    def _finalize(self, result: OCRResult) -> OCRResult:
        """Normalise Devanagari digits in-place and return."""
        result.full_text = _normalize(result.full_text)
        for w in result.words:
            w.text = _normalize(w.text)
        return result

    def _merge(self, primary: OCRResult, secondary: OCRResult) -> OCRResult:
        """Add non-overlapping secondary words to primary."""
        merged = list(primary.words)
        for sw in secondary.words:
            overlap = any(
                abs(sw.bbox.x - pw.bbox.x) < 25 and abs(sw.bbox.y - pw.bbox.y) < 25
                for pw in primary.words
            )
            if not overlap:
                merged.append(sw)
        merged.sort(key=lambda w: (w.bbox.y, w.bbox.x))
        logger.info("OCR merge: %d + %d → %d words",
                    len(primary.words), len(secondary.words), len(merged))
        return OCRResult(
            full_text=" ".join(w.text for w in merged),
            words=merged,
            image_width=primary.image_width or secondary.image_width,
            image_height=primary.image_height or secondary.image_height,
        )