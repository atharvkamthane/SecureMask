"""Ground-truth annotation schema and validation tooling for evaluation.

Each test image has a companion JSON sidecar file containing:
  - image_path: relative or absolute path to the image
  - true_document_type: one of aadhaar | pan | passport | driving_license | voter_id
  - fields: list of annotated fields, each with:
      - field_name: canonical field name (e.g. "aadhaar_number", "name", "dob")
      - true_value: ground-truth text value
      - bbox: [x, y, w, h] in pixels

CLI Usage::
    python -m securemask.eval.annotations_schema --validate --test-dir <path>
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List

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
        ann.image_path = str(img_path)
        annotations.append(ann)

    if not annotations:
        logger.warning("No annotated images found in %s", directory)

    return annotations


def validate_test_set(directory: str | Path, min_target_per_class: int = 30) -> dict[str, Any]:
    """Inspect and validate test dataset integrity, reporting class balance and field counts."""
    directory = Path(directory)
    annotations = load_test_set(directory)

    errors: list[str] = []
    warnings: list[str] = []
    class_counts: Counter[str] = Counter()
    total_fields = 0
    fields_per_class: Counter[str] = Counter()

    for ann in annotations:
        doc_type = ann.true_document_type
        if doc_type not in VALID_DOCUMENT_TYPES:
            errors.append(f"{ann.image_path}: invalid true_document_type '{doc_type}'")
        class_counts[doc_type] += 1

        if not ann.fields:
            warnings.append(f"{ann.image_path}: zero fields annotated")

        for f in ann.fields:
            total_fields += 1
            fields_per_class[doc_type] += 1
            if not f.field_name:
                errors.append(f"{ann.image_path}: empty field_name")
            if not f.true_value:
                warnings.append(f"{ann.image_path} ({f.field_name}): empty true_value")
            if len(f.bbox) != 4 or f.bbox[2] <= 0 or f.bbox[3] <= 0:
                errors.append(f"{ann.image_path} ({f.field_name}): invalid bbox {f.bbox}")

    # Check class sample balance
    thin_classes: list[str] = []
    for doc_type in sorted(VALID_DOCUMENT_TYPES):
        cnt = class_counts[doc_type]
        if cnt < min_target_per_class:
            thin_classes.append(doc_type)
            warnings.append(f"Class '{doc_type}' has only {cnt} samples (< target {min_target_per_class}).")

    return {
        "valid": len(errors) == 0,
        "total_images": len(annotations),
        "class_counts": dict(class_counts),
        "total_fields": total_fields,
        "fields_per_class": dict(fields_per_class),
        "thin_classes": thin_classes,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate SecureMask test dataset annotations.")
    parser.add_argument("--test-dir", type=Path, required=True, help="Directory containing images and JSON sidecars")
    parser.add_argument("--validate", action="store_true", help="Perform comprehensive schema and balance validation")
    parser.add_argument("--min-per-class", type=int, default=30, help="Minimum sample target per class")
    args = parser.parse_args(argv)

    if not args.test_dir.exists():
        print(f"Error: Directory '{args.test_dir}' does not exist.")
        sys.exit(1)

    print("=" * 70)
    print(f"SECUREMASK TEST SET VALIDATION: {args.test_dir}")
    print("=" * 70)

    report = validate_test_set(args.test_dir, min_target_per_class=args.min_per_class)

    print(f"Total Annotated Images: {report['total_images']}")
    print(f"Total Annotated Fields: {report['total_fields']}")
    print("\nPer-Class Image Breakdown:")
    print("-" * 50)
    for doc_type in sorted(VALID_DOCUMENT_TYPES):
        cnt = report["class_counts"].get(doc_type, 0)
        fcnt = report["fields_per_class"].get(doc_type, 0)
        status = "OK" if cnt >= args.min_per_class else f"THIN (<{args.min_per_class})"
        print(f"  {doc_type:<18} {cnt:>4} images ({fcnt:>4} fields)  [{status}]")
    print("-" * 50)

    if report["warnings"]:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for w in report["warnings"][:10]:
            print(f"  [!] {w}")
        if len(report["warnings"]) > 10:
            print(f"  ... and {len(report['warnings']) - 10} more warnings.")

    if report["errors"]:
        print(f"\nErrors ({len(report['errors'])}):")
        for e in report["errors"][:10]:
            print(f"  [X] {e}")
        if len(report["errors"]) > 10:
            print(f"  ... and {len(report['errors']) - 10} more errors.")
        sys.exit(1)
    else:
        print("\nValidation Result: PASSED (Schema valid)")


if __name__ == "__main__":
    main()
