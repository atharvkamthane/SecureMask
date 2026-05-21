"""Image utility helpers + preprocessing coordinator.

The key addition is `prepare_scan_images()`, which runs all preprocessing
once per scan and returns named paths for each OCR engine. This prevents
the old pattern where each engine re-read and re-processed the raw file.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from securemask.core.preprocessor import save_preprocessed_variants


def load_image(path: str | Path) -> Image.Image:
    """Load an image from disk as a PIL Image (RGB)."""
    return Image.open(path).convert("RGB")


def pil_to_cv(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR array."""
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def cv_to_pil(image: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR array to PIL Image (RGB)."""
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def ensure_processable_image(path: str | Path, output_dir: str | Path) -> Path:
    """Ensure image is readable and save a processable PNG copy.

    No upscaling here — upscaling is handled inside preprocessor.py so
    all coordinate transforms stay consistent.
    """
    path = Path(path)
    output = Path(output_dir) / "processable.png"
    img = Image.open(path).convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, "PNG")
    return output


def prepare_scan_images(
    image_path: str | Path,
    scan_dir: str | Path,
) -> dict[str, Path]:
    """Preprocess the uploaded document once and return per-engine image paths.

    Call this at the start of each scan (e.g. in main.py / routes.py) and
    pass the returned paths down to OCREngine.extract().

    Returns a dict with keys:
      'color'         → deskewed JPEG for EasyOCR
      'enhanced_gray' → sharpened grayscale PNG for PaddleOCR
      'binary'        → adaptive-thresholded PNG for EasyOCR / archival

    Example usage in routes.py:
        scan_paths = prepare_scan_images(upload_path, storage / scan_id)
        ocr_result = ocr_engine.extract(
            image_path=upload_path,
            preprocessed_color_path=scan_paths['color'],
            preprocessed_gray_path=scan_paths['enhanced_gray'],
        )
    """
    processed_dir = Path(scan_dir) / "processed"
    return save_preprocessed_variants(image_path, processed_dir)