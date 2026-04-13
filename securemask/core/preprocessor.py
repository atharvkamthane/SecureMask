"""OpenCV image preprocessing pipeline for OCR.

Steps: load → grayscale → deskew → denoise → CLAHE → Otsu binarization
Returns both preprocessed grayscale (for OCR) and original color (for redaction).
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def load_cv_image(path: str | Path) -> np.ndarray:
    """Load an image from disk as a BGR numpy array."""
    img = cv2.imread(str(path))
    if img is None:
        pil = Image.open(path).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _deskew(image: np.ndarray) -> np.ndarray:
    """Detect rotation angle using Hough line transform and correct it."""
    gray = _to_grayscale(image)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                            minLineLength=100, maxLineGap=10)
    if lines is None or len(lines) < 3:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        # Only consider near-horizontal lines (±30°)
        if -30 < angle < 30:
            angles.append(angle)

    if not angles:
        return image

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return image  # already straight

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (w, h),
                              flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)
    return rotated


def _denoise(image: np.ndarray) -> np.ndarray:
    """Apply fast non-local means denoising."""
    if len(image.shape) == 2:
        return cv2.fastNlMeansDenoising(image, h=10)
    return cv2.fastNlMeansDenoisingColored(image, h=10, hForColorComponents=10)


def _clahe(gray: np.ndarray) -> np.ndarray:
    """Apply CLAHE contrast enhancement."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _otsu_binarize(gray: np.ndarray) -> np.ndarray:
    """Apply Otsu's thresholding for binarization."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def preprocess(image_path: str | Path) -> tuple[np.ndarray, np.ndarray, Image.Image]:
    """Full preprocessing pipeline.

    Returns:
        (preprocessed_gray_for_ocr, original_color_for_redaction, pil_color_image)
    """
    raw = load_cv_image(image_path)

    # Step 1: Deskew the color image
    color = _deskew(raw)

    # Step 2-3: Convert to grayscale and denoise
    gray = _to_grayscale(color)
    gray = _denoise(gray)

    # Step 4: CLAHE contrast enhancement
    enhanced = _clahe(gray)

    # Step 5: Otsu binarization (for OCR input)
    binary = _otsu_binarize(enhanced)

    # Convert color image to PIL for redaction downstream
    pil_color = Image.fromarray(cv2.cvtColor(color, cv2.COLOR_BGR2RGB))

    return binary, color, pil_color


def preprocess_for_paddle(image_path: str | Path) -> np.ndarray:
    """Return the deskewed + CLAHE enhanced image for PaddleOCR (expects BGR or gray)."""
    raw = load_cv_image(image_path)
    color = _deskew(raw)
    gray = _to_grayscale(color)
    denoised = _denoise(gray)
    enhanced = _clahe(denoised)
    return enhanced
