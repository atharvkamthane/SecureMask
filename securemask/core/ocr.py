from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

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


def extract_text_and_boxes(image_path: str | Path) -> OCRResult:
    import pytesseract

    image = Image.open(image_path).convert("RGB")
    processed = preprocess_for_ocr(image)
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


def ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
