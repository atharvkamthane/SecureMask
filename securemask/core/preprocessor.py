"""OpenCV image preprocessing pipeline for OCR.

Steps: load → upscale (if small) → deskew → denoise → CLAHE → sharpen → binarize
Returns multiple image variants tuned for different OCR engines:
  - binary_for_paddle: high-contrast B&W for PaddleOCR / EasyOCR
  - enhanced_color:    deskewed + CLAHE color image for Google Vision (works best on color)
  - pil_color:         PIL version of enhanced_color for redaction downstream
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

# Upscale images narrower than this to improve OCR on small documents
MIN_USEFUL_WIDTH = 1000          # pixels
MAX_UPSCALE_FACTOR = 3.0        # don't enlarge beyond 3×

# Sharpening kernel (mild unsharp mask — improves character edges)
_SHARPEN_KERNEL = np.array([
    [0, -0.5,  0],
    [-0.5,  3, -0.5],
    [0, -0.5,  0],
], dtype=np.float32)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def load_cv_image(path: str | Path) -> np.ndarray:
    """Load an image from disk as a BGR numpy array."""
    img = cv2.imread(str(path))
    if img is None:
        # cv2 can't handle non-ASCII paths on Windows; fall back to PIL
        pil = Image.open(path).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _upscale_if_small(image: np.ndarray) -> np.ndarray:
    """Upscale small images before OCR — biggest single accuracy win.

    OCR engines struggle under ~1000 px wide. We scale with LANCZOS4
    (high-quality) and cap at 3× to avoid hallucinations on huge docs.
    """
    h, w = image.shape[:2]
    if w >= MIN_USEFUL_WIDTH:
        return image

    factor = min(MIN_USEFUL_WIDTH / w, MAX_UPSCALE_FACTOR)
    new_w = int(w * factor)
    new_h = int(h * factor)
    interp = cv2.INTER_LANCZOS4 if factor > 1.5 else cv2.INTER_LINEAR
    return cv2.resize(image, (new_w, new_h), interpolation=interp)


def _deskew(image: np.ndarray) -> np.ndarray:
    """Detect rotation angle using Hough line transform and correct it."""
    gray = _to_grayscale(image)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
    )
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
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _denoise(image: np.ndarray) -> np.ndarray:
    """Non-local means denoising (tuned for scanned ID documents)."""
    if len(image.shape) == 2:
        # Grayscale — h=7 is gentler than default 10; preserves thin strokes
        return cv2.fastNlMeansDenoising(image, h=7, templateWindowSize=7, searchWindowSize=21)
    return cv2.fastNlMeansDenoisingColored(
        image, h=7, hForColorComponents=7, templateWindowSize=7, searchWindowSize=21
    )


def _clahe(gray: np.ndarray) -> np.ndarray:
    """CLAHE contrast enhancement — equalises lighting without blowing highlights."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _sharpen(gray: np.ndarray) -> np.ndarray:
    """Mild unsharp mask to crisp up character edges after CLAHE."""
    return cv2.filter2D(gray, -1, _SHARPEN_KERNEL)


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Two-stage binarization: try adaptive first, fall back to Otsu.

    Adaptive thresholding handles uneven lighting far better than global Otsu
    (e.g. Aadhaar cards photographed at an angle under mixed light).
    """
    # Adaptive (Gaussian) thresholding — best for uneven lighting
    adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=31, C=10,
    )

    # Morphological cleanup: remove salt-and-pepper specks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    adaptive = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel, iterations=1)

    # If adaptive produced very few dark pixels (overexposed scan), use Otsu
    dark_ratio = np.sum(adaptive == 0) / adaptive.size
    if dark_ratio < 0.02 or dark_ratio > 0.60:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return otsu

    return adaptive


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def preprocess(
    image_path: str | Path,
) -> tuple[np.ndarray, np.ndarray, Image.Image]:
    """Full preprocessing pipeline.

    Returns:
        (binary_for_ocr, deskewed_color_bgr, pil_color_image)
        - binary_for_ocr    → pass to PaddleOCR / EasyOCR
        - deskewed_color_bgr → pass to Google Vision (or redaction)
        - pil_color_image   → PIL version of color image for redaction engine
    """
    raw = load_cv_image(image_path)

    # 1. Upscale small images — critical for accuracy on phone photos of IDs
    raw = _upscale_if_small(raw)

    # 2. Deskew color image (so coordinates stay consistent with the color layer)
    color = _deskew(raw)

    # 3. Grayscale + denoise
    gray = _to_grayscale(color)
    gray = _denoise(gray)

    # 4. CLAHE contrast enhancement
    enhanced = _clahe(gray)

    # 5. Mild sharpen (improves character edge definition)
    sharpened = _sharpen(enhanced)

    # 6. Adaptive / Otsu binarization for OCR engines that prefer B&W
    binary = _binarize(sharpened)

    pil_color = Image.fromarray(cv2.cvtColor(color, cv2.COLOR_BGR2RGB))
    return binary, color, pil_color


def preprocess_for_paddle(image_path: str | Path) -> np.ndarray:
    """Return the enhanced grayscale for PaddleOCR.

    PaddleOCR's internal binarizer works better when given the sharpened
    grayscale rather than a pre-binarized image (avoids double thresholding).
    """
    raw = load_cv_image(image_path)
    raw = _upscale_if_small(raw)
    color = _deskew(raw)
    gray = _to_grayscale(color)
    denoised = _denoise(gray)
    enhanced = _clahe(denoised)
    sharpened = _sharpen(enhanced)
    return sharpened


def save_preprocessed_variants(
    image_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Preprocess once and save named variants for each OCR engine.

    Returns a dict with keys: 'color', 'enhanced_gray', 'binary'
    so each OCR engine can load its preferred format without re-running
    the expensive preprocessing pipeline.
    """
    binary, color, pil_color = preprocess(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # Color (JPEG, 90% quality) for Google Vision
    color_path = output_dir / "color.jpg"
    pil_color.save(str(color_path), "JPEG", quality=90)
    paths["color"] = color_path

    # Enhanced grayscale for PaddleOCR
    gray_img = _clahe(_to_grayscale(color))
    gray_img = _sharpen(gray_img)
    gray_path = output_dir / "enhanced_gray.png"
    cv2.imwrite(str(gray_path), gray_img)
    paths["enhanced_gray"] = gray_path

    # Binary for EasyOCR / archival
    binary_path = output_dir / "binary.png"
    cv2.imwrite(str(binary_path), binary)
    paths["binary"] = binary_path

    return paths

