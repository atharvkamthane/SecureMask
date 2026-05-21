"""One-off pipeline test for Aadhaar bbox tuning."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

IMAGE = Path(
    r"C:\Users\Atharv\.cursor\projects\d-SecureMask\assets"
    r"\c__Users_Atharv_AppData_Roaming_Cursor_User_workspaceStorage_57769352b4d43870738657e33bbebc6f_images_image-8c0ec328-35cd-4e8d-b9a7-6fcdd80acab8.png"
)


def main() -> None:
    from PIL import Image
    from securemask.core.ocr import OCREngine, _get_paddle_reader_en, _get_easyocr_reader
    from securemask.core.extractor import FieldExtractor
    from securemask.utils.image_utils import save_preprocessed_variants

    print("=== OCR reader pre-warm ===")
    paddle = _get_paddle_reader_en()
    print(f"Paddle reader: {'OK' if paddle else 'None'}")
    easy = _get_easyocr_reader()
    print(f"EasyOCR reader: {'OK' if easy else 'None'}")

    variants = save_preprocessed_variants(str(IMAGE), job_id="test-extract")
    engine = OCREngine()
    ocr = engine.extract(
        IMAGE,
        preprocessed_color_path=variants.get("color"),
    )
    print(f"\n=== OCR ===")
    print(f"Image: {ocr.image_width}x{ocr.image_height}, words={len(ocr.words)}")
    print(f"Preview: {ocr.full_text[:180]}...")

    extractor = FieldExtractor()
    fields = extractor.extract(ocr, Image.open(IMAGE), "aadhaar", str(IMAGE))

    print(f"\n=== Fields ({len(fields)}) ===")
    for f in sorted(fields, key=lambda x: x.field_name):
        b = f.bounding_box
        pct_w = round(b.width / max(ocr.image_width, 1) * 100, 1)
        pct_h = round(b.height / max(ocr.image_height, 1) * 100, 1)
        print(
            f"  {f.field_name:16} {str(f.field_value)[:40]:40} "
            f"bbox=({b.x},{b.y},{b.width}x{b.height}) "
            f"[{pct_w}%w {pct_h}%h] conf={f.confidence:.2f}"
        )


if __name__ == "__main__":
    main()
