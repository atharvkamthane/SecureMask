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

PADDLE_CONFIDENCE_THRESHOLD = 0.72
MIN_WORDS_THRESHOLD = 5


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
    """Lazy-init PaddleOCR reader (cached)."""
    try:
        from paddleocr import PaddleOCR
        reader = PaddleOCR(
            lang="en",
            use_angle_cls=True,
            use_gpu=False,
            show_log=False,
        )
        logger.info("PaddleOCR engine initialised")
        return reader
    except Exception as exc:
        logger.warning("PaddleOCR unavailable: %s", exc)
        return None


def _paddle_ocr(image_path: str) -> OCRResult | None:
    """Extract text using PaddleOCR."""
    reader = _get_paddle_reader()
    if reader is None:
        return None

    try:
        result = reader.ocr(str(image_path), cls=True)
        if result is None or not result[0]:
            return None

        img = cv2.imread(str(image_path))
        if img is None:
            img = np.array(Image.open(image_path).convert("RGB"))
        h, w = img.shape[:2]

        words: list[OCRWord] = []
        parts: list[str] = []

        for line in result[0]:
            points, (text, conf) = line
            text = str(text).strip()
            if not text:
                continue

            # points is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            xs = [int(p[0]) for p in points]
            ys = [int(p[1]) for p in points]
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

        full_text = " ".join(parts)
        return OCRResult(full_text=full_text, words=words, image_width=w, image_height=h)

    except Exception as exc:
        logger.error("PaddleOCR extraction failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Google Cloud Vision fallback
# ---------------------------------------------------------------------------

def _google_vision_available() -> bool:
    """Check whether GCP Vision credentials are set up."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    if GCP_CREDENTIALS_PATH.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GCP_CREDENTIALS_PATH)
        return True
    return False


def _google_vision_ocr(image_path: str) -> OCRResult | None:
    """Extract text using Google Cloud Vision API."""
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
        results = reader.readtext(img, detail=1)
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
    except Exception:
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

        # Fallback 1: Google Vision
        logger.info("PaddleOCR below threshold (%.2f/%d words), trying Google Vision",
                     result.avg_confidence if result else 0, len(result.words) if result else 0)
        vision_result = _google_vision_ocr(image_path)
        if vision_result and len(vision_result.words) >= MIN_WORDS_THRESHOLD:
            logger.info("Google Vision: %d words, avg_conf=%.2f", len(vision_result.words), vision_result.avg_confidence)
            return vision_result

        # Fallback 2: EasyOCR
        logger.info("Google Vision unavailable/failed, trying EasyOCR")
        easy_result = _easyocr_fallback(image_path)
        if easy_result and easy_result.words:
            logger.info("EasyOCR: %d words, avg_conf=%.2f", len(easy_result.words), easy_result.avg_confidence)
            return easy_result

        # Use whatever we have
        if result and result.words:
            return result
        if vision_result and vision_result.words:
            return vision_result

        logger.error("All OCR engines failed for %s", image_path)
        return OCRResult(full_text="", words=[], image_width=0, image_height=0)
