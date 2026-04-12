from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

from securemask.config import STORAGE_DIR
from securemask.models.detected_field import BoundingBox
from securemask.utils.image_utils import preprocess_for_ocr


@dataclass
class OCRWord:
    text: str
    box: BoundingBox
    confidence: float


@dataclass
class OCRResult:
    text: str
    words: list[OCRWord]
    image_width: int
    image_height: int


@lru_cache(maxsize=1)
def _easyocr_reader():
    import easyocr

    model_dir = STORAGE_DIR / "easyocr"
    model_dir.mkdir(parents=True, exist_ok=True)
    return easyocr.Reader(["en"], gpu=False, verbose=False, model_storage_directory=str(model_dir), user_network_directory=str(model_dir))


def _extract_with_tesseract(processed: Image.Image, image: Image.Image) -> OCRResult:
    import pytesseract

    text = pytesseract.image_to_string(processed, lang="eng")
    data = pytesseract.image_to_data(processed, lang="eng", output_type=pytesseract.Output.DICT)
    words: list[OCRWord] = []
    for idx, raw_word in enumerate(data.get("text", [])):
        word = str(raw_word).strip()
        if not word:
            continue
        try:
            confidence = float(data["conf"][idx])
        except (ValueError, TypeError):
            confidence = 0.0
        if confidence < 0:
            confidence = 0.0
        words.append(
            OCRWord(
                text=word,
                box=BoundingBox(
                    int(data["left"][idx]),
                    int(data["top"][idx]),
                    int(data["width"][idx]),
                    int(data["height"][idx]),
                ),
                confidence=min(confidence / 100.0, 1.0),
            )
        )
    return OCRResult(text=text, words=words, image_width=image.width, image_height=image.height)


def _extract_with_easyocr(processed: Image.Image, image: Image.Image) -> OCRResult:
    import numpy as np

    reader = _easyocr_reader()
    results = reader.readtext(np.array(processed))
    words: list[OCRWord] = []
    parts: list[str] = []
    for entry in results:
        points, text, confidence = entry
        if not str(text).strip():
            continue
        xs = [int(point[0]) for point in points]
        ys = [int(point[1]) for point in points]
        x = min(xs)
        y = min(ys)
        width = max(xs) - x
        height = max(ys) - y
        words.append(OCRWord(text=str(text), box=BoundingBox(x, y, width, height), confidence=float(confidence)))
        parts.append(str(text))
    return OCRResult(text=" ".join(parts), words=words, image_width=image.width, image_height=image.height)


def extract_text_and_boxes(image_path: str | Path) -> OCRResult:
    image = Image.open(image_path).convert("RGB")
    processed = preprocess_for_ocr(image)
    errors: list[str] = []
    try:
        return _extract_with_tesseract(processed, image)
    except Exception as exc:
        errors.append(f"Tesseract failed: {exc}")
    try:
        return _extract_with_easyocr(processed, image)
    except Exception as exc:
        errors.append(f"EasyOCR failed: {exc}")
    raise RuntimeError("OCR unavailable. " + " | ".join(errors))


def ocr_available() -> bool:
    try:
        image = Image.new("RGB", (4, 4), color="white")
        _extract_with_tesseract(image, image)
        return True
    except Exception:
        try:
            _easyocr_reader()
            return True
        except Exception:
            return False
