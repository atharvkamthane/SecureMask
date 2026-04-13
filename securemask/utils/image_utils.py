"""Image utility helpers."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def load_image(path: str | Path) -> Image.Image:
    """Load an image from disk as a PIL Image."""
    return Image.open(path).convert("RGB")


def pil_to_cv(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR array."""
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def cv_to_pil(image: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR array to PIL Image."""
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def ensure_processable_image(path: str | Path, output_dir: str | Path) -> Path:
    """Ensure image is readable and save a processable copy.

    No upscaling — saves at original resolution to preserve coordinate alignment.
    """
    path = Path(path)
    output = Path(output_dir) / "processable.png"
    img = Image.open(path).convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, "PNG")
    return output
