from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


def load_image(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    import cv2
    import numpy as np

    gray = ImageOps.grayscale(image)
    arr = np.array(gray)
    arr = cv2.bilateralFilter(arr, 9, 75, 75)
    arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    return Image.fromarray(arr)


def pdf_to_image(pdf_path: str | Path, output_path: str | Path) -> Path:
    from pdf2image import convert_from_path

    pages = convert_from_path(str(pdf_path), first_page=1, last_page=1)
    if not pages:
        raise ValueError("PDF did not contain any pages")
    output = Path(output_path)
    pages[0].convert("RGB").save(output, "PNG")
    return output


def ensure_processable_image(input_path: str | Path, output_path: str | Path) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    if input_path.suffix.lower() == ".pdf":
        return pdf_to_image(input_path, output_path)

    image = load_image(input_path)
    image.save(output_path, "PNG")
    return output_path


def zone_bounds(zone: str, image_height: int) -> tuple[int, int]:
    if zone == "top":
        return 0, int(image_height * 0.4)
    if zone == "middle":
        return int(image_height * 0.25), int(image_height * 0.75)
    if zone == "bottom":
        return int(image_height * 0.6), image_height
    return 0, image_height
