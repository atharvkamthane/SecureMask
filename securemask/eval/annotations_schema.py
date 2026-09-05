"""Ground-truth annotation schema for evaluation.

Each test image has a companion JSON sidecar file containing:
  - image_path: relative or absolute path to the image
  - true_document_type: one of aadhaar | pan | passport | driving_license | voter_id
  - fields: list of annotated fields, each with:
      - field_name: canonical field name (e.g. "aadhaar_number", "name", "dob")
      - true_value: ground-truth text value
      - bbox: [x, y, w, h] in pixels

Example JSON::

    {
      "image_path": "aadhaar_001.jpg",
      "true_document_type": "aadhaar",
      "fields": [
        {"field_name": "aadhaar_number", "true_value": "2530 0479 3566", "bbox": [335, 830, 330, 52]},
        {"field_name": "name", "true_value": "Atharv Murhari Kamthane", "bbox": [330, 312, 320, 36]},
        {"field_name": "dob", "true_value": "15/04/2006", "bbox": [550, 372, 135, 34]}
      ]
    }
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Supported document type labels
VALID_DOCUMENT_TYPES = frozenset({
    "aadhaar", "pan", "passport", "driving_license", "voter_id",
})

# Common image extensions to look for when scanning a test directory
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"})


@dataclass
class FieldAnnotation:
    """A single annotated field on a document image.

    Attributes:
        field_name: Canonical field identifier (e.g. ``"aadhaar_number"``).
        true_value: Ground-truth text value for the field.
        bbox: Bounding box in pixels as ``[x, y, width, height]``.
    """
    field_name: str
    true_value: str
    bbox: list[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class ImageAnnotation:
    """Ground-truth annotation for a single test image.

    Attributes:
        image_path: Path to the image (relative or absolute).
        true_document_type: One of the five supported document types.
        fields: List of :class:`FieldAnnotation` entries.
    """
    image_path: str
    true_document_type: str
    fields: List[FieldAnnotation] = field(default_factory=list)


def save_annotation(annotation: ImageAnnotation, json_path: str | Path) -> None:
    """Serialize an :class:`ImageAnnotation` to a JSON file."""
    data = asdict(annotation)
    Path(json_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_annotation(json_path: str | Path) -> ImageAnnotation:
    """Deserialize an :class:`ImageAnnotation` from a JSON file."""
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    fields = [
        FieldAnnotation(
            field_name=f["field_name"],
            true_value=f["true_value"],
            bbox=f.get("bbox", [0, 0, 0, 0]),
        )
        for f in raw.get("fields", [])
    ]
    return ImageAnnotation(
        image_path=raw["image_path"],
        true_document_type=raw["true_document_type"],
        fields=fields,
    )


def load_test_set(directory: str | Path) -> list[ImageAnnotation]:
    """Walk *directory* and pair each image with its ``<stem>.json`` sidecar.

    Returns a list of :class:`ImageAnnotation` objects, sorted by image path.
    Only images that have a matching ``.json`` file are included.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Test directory not found: {directory}")

    annotations: list[ImageAnnotation] = []
    for img_path in sorted(directory.rglob("*")):
        if img_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        json_path = img_path.with_suffix(".json")
        if not json_path.exists():
            logger.warning("No annotation JSON for %s — skipping", img_path.name)
            continue
        ann = load_annotation(json_path)
        # Resolve image_path relative to directory if needed
        ann.image_path = str(img_path)
        annotations.append(ann)

    if not annotations:
        logger.warning("No annotated images found in %s", directory)

    return annotations
