"""OpenCV image preprocessing pipeline for OCR.

Steps: load → upscale → deskew → denoise → CLAHE → sharpen → binarize
Variants saved: color.jpg (for OCR engines), enhanced_gray.png, binary.png

NOTE on PaddleOCR 3.x: its UVDoc + orientation sub-models require a COLOR
image. Always pass 'color' variant to PaddleOCR — never enhanced_gray or binary.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

MIN_USEFUL_WIDTH = 1000      # upscale anything narrower than this
MAX_UPSCALE_FACTOR = 3.0

_SHARPEN_KERNEL = np.array([
    [0, -0.5,  0],
    [-0.5,  3, -0.5],
    [0, -0.5,  0],
], dtype=np.float32)


# ------------------------------------------------------------------
# Individual steps
# ------------------------------------------------------------------

def load_cv_image(path: str | Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        pil = Image.open(path).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _upscale_if_small(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    if w >= MIN_USEFUL_WIDTH:
        return image
    factor = min(MIN_USEFUL_WIDTH / w, MAX_UPSCALE_FACTOR)
    new_w, new_h = int(w * factor), int(h * factor)
    interp = cv2.INTER_LANCZOS4 if factor > 1.5 else cv2.INTER_LINEAR
    return cv2.resize(image, (new_w, new_h), interpolation=interp)


def _deskew(image: np.ndarray) -> np.ndarray:
    gray  = _to_grayscale(image)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                             minLineLength=100, maxLineGap=10)
    if lines is None or len(lines) < 3:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if -30 < angle < 30:
            angles.append(angle)

    if not angles:
        return image
    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return image

    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
    return cv2.warpAffine(image, M, (w, h),
                           flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REPLICATE)


def _denoise(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return cv2.fastNlMeansDenoising(image, h=7,
                                         templateWindowSize=7, searchWindowSize=21)
    return cv2.fastNlMeansDenoisingColored(image, h=7, hForColorComponents=7,
                                            templateWindowSize=7, searchWindowSize=21)


def _clahe(gray: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def _sharpen(gray: np.ndarray) -> np.ndarray:
    return cv2.filter2D(gray, -1, _SHARPEN_KERNEL)


def _binarize(gray: np.ndarray) -> np.ndarray:
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=31, C=10,
    )
    kernel   = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    adaptive = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel, iterations=1)

    dark_ratio = np.sum(adaptive == 0) / adaptive.size
    if dark_ratio < 0.02 or dark_ratio > 0.60:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return otsu
    return adaptive


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def preprocess(image_path: str | Path) -> tuple[np.ndarray, np.ndarray, Image.Image]:
    """Full pipeline.

    Returns:
        (binary_for_ocr, deskewed_color_bgr, pil_color)
    """
    raw   = load_cv_image(image_path)
    raw   = _upscale_if_small(raw)
    color = _deskew(raw)

    gray     = _to_grayscale(color)
    gray     = _denoise(gray)
    enhanced = _clahe(gray)
    sharpened = _sharpen(enhanced)
    binary   = _binarize(sharpened)

    pil_color = Image.fromarray(cv2.cvtColor(color, cv2.COLOR_BGR2RGB))
    return binary, color, pil_color


def preprocess_for_paddle(image_path: str | Path) -> np.ndarray:
    """Return enhanced grayscale for legacy PaddleOCR (< 3.x).
    
    PaddleOCR 3.x should use the COLOR image instead.
    """
    raw   = load_cv_image(image_path)
    raw   = _upscale_if_small(raw)
    color = _deskew(raw)
    gray  = _to_grayscale(color)
    gray  = _denoise(gray)
    return _sharpen(_clahe(gray))


def save_preprocessed_variants(
    image_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Preprocess once, save three variants, return their paths.

    Keys:
      'color'         — deskewed JPEG, best for PaddleOCR 3.x and EasyOCR
      'enhanced_gray' — sharpened grayscale PNG, kept for legacy / archival
      'binary'        — adaptive-threshold PNG for archival

    ALWAYS pass 'color' to PaddleOCR 3.x — its sub-models need color input.
    """
    binary, color, pil_color = preprocess(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    color_path = output_dir / "color.jpg"
    pil_color.save(str(color_path), "JPEG", quality=92)
    paths["color"] = color_path

    gray_img  = _sharpen(_clahe(_to_grayscale(color)))
    gray_path = output_dir / "enhanced_gray.png"
    cv2.imwrite(str(gray_path), gray_img)
    paths["enhanced_gray"] = gray_path

    binary_path = output_dir / "binary.png"
    cv2.imwrite(str(binary_path), binary)
    paths["binary"] = binary_path

    return paths