"""OpenCV-based annotation CLI for creating ground-truth JSON sidecar files.

Usage::

    python -m securemask.eval.annotate_cli --image-dir <path>

For each image in *image-dir*:
  1. Opens an OpenCV window showing the image.
  2. Click-and-drag to draw bounding boxes.
  3. Terminal prompts for document_type (first image only or ``t`` to change),
     field_name and true_value for each box.
  4. Saves ``<image_stem>.json`` next to the image.

Keyboard shortcuts:
  n — save & advance to next image
  u — undo last drawn box
  t — change document type for current image
  q — quit (saves current work first)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from securemask.eval.annotations_schema import (
    FieldAnnotation,
    ImageAnnotation,
    IMAGE_EXTENSIONS,
    VALID_DOCUMENT_TYPES,
    save_annotation,
)


def _draw_boxes(img: np.ndarray, boxes: list[dict], current_box: list[int] | None = None) -> np.ndarray:
    """Draw all committed boxes plus optional in-progress box."""
    vis = img.copy()
    for i, b in enumerate(boxes):
        x, y, w, h = b["bbox"]
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)
        label = f"{i}: {b['field_name']}"
        cv2.putText(vis, label, (x, max(y - 8, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    if current_box and len(current_box) == 4:
        x, y, w, h = current_box
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 2)
    return vis


def _annotate_image(img_path: Path, document_type: str) -> tuple[ImageAnnotation | None, str]:
    """Interactively annotate a single image. Returns (annotation, document_type)."""
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"  [!] Could not read {img_path.name}, skipping.")
        return None, document_type

    win_name = f"Annotate: {img_path.name}"
    boxes: list[dict] = []
    drawing = False
    ix, iy = 0, 0
    current_box: list[int] | None = None

    def mouse_cb(event, x, y, flags, param):
        nonlocal drawing, ix, iy, current_box
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            ix, iy = x, y
            current_box = None
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            bx = min(ix, x)
            by = min(iy, y)
            bw = abs(x - ix)
            bh = abs(y - iy)
            current_box = [bx, by, bw, bh]
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            bx = min(ix, x)
            by = min(iy, y)
            bw = abs(x - ix)
            bh = abs(y - iy)
            if bw > 5 and bh > 5:
                current_box = [bx, by, bw, bh]
            else:
                current_box = None

    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win_name, mouse_cb)

    print(f"\n--- {img_path.name}  [doc_type: {document_type}] ---")
    print("  Draw bbox → press ENTER in terminal to label it.")
    print("  Keys: n=next  u=undo  t=change type  q=quit")

    while True:
        vis = _draw_boxes(img, boxes, current_box)
        cv2.imshow(win_name, vis)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("n"):
            break
        elif key == ord("u"):
            if boxes:
                removed = boxes.pop()
                print(f"  Undid: {removed['field_name']}")
            else:
                print("  Nothing to undo.")
        elif key == ord("t"):
            new_type = input(f"  New doc type ({', '.join(sorted(VALID_DOCUMENT_TYPES))}): ").strip()
            if new_type in VALID_DOCUMENT_TYPES:
                document_type = new_type
                print(f"  → type set to {document_type}")
            else:
                print(f"  Invalid type: {new_type}")
        elif key == ord("q"):
            cv2.destroyAllWindows()
            ann = ImageAnnotation(
                image_path=img_path.name,
                true_document_type=document_type,
                fields=[FieldAnnotation(**b) for b in boxes],
            )
            return ann, "__QUIT__"
        elif key == 13:  # Enter
            if current_box and current_box[2] > 5 and current_box[3] > 5:
                field_name = input("  field_name: ").strip()
                true_value = input("  true_value: ").strip()
                if field_name:
                    boxes.append({
                        "field_name": field_name,
                        "true_value": true_value,
                        "bbox": list(current_box),
                    })
                    print(f"  [+] Added {field_name} = {true_value}")
                    current_box = None
                else:
                    print("  Skipped (empty field_name).")
            else:
                print("  No bbox drawn yet — draw first, then press Enter.")

    cv2.destroyAllWindows()

    ann = ImageAnnotation(
        image_path=img_path.name,
        true_document_type=document_type,
        fields=[FieldAnnotation(**b) for b in boxes],
    )
    return ann, document_type


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Annotate document images with ground-truth bounding boxes and field values.",
    )
    parser.add_argument("--image-dir", required=True, type=Path,
                        help="Directory containing images to annotate.")
    args = parser.parse_args(argv)

    image_dir: Path = args.image_dir
    if not image_dir.is_dir():
        print(f"Error: {image_dir} is not a directory.")
        sys.exit(1)

    images = sorted(
        p for p in image_dir.iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        print(f"No images found in {image_dir}")
        sys.exit(1)

    print(f"Found {len(images)} images in {image_dir}")
    doc_type = input(f"Default document type ({', '.join(sorted(VALID_DOCUMENT_TYPES))}): ").strip()
    if doc_type not in VALID_DOCUMENT_TYPES:
        print(f"Invalid type '{doc_type}', defaulting to 'aadhaar'")
        doc_type = "aadhaar"

    for img_path in images:
        json_path = img_path.with_suffix(".json")
        if json_path.exists():
            overwrite = input(f"  {json_path.name} exists. Overwrite? (y/N): ").strip().lower()
            if overwrite != "y":
                print("  Skipped.")
                continue

        ann, doc_type = _annotate_image(img_path, doc_type)
        if doc_type == "__QUIT__":
            if ann and ann.fields:
                save_annotation(ann, json_path)
                print(f"  Saved {json_path.name} ({len(ann.fields)} fields)")
            print("Quitting.")
            break

        if ann and ann.fields:
            save_annotation(ann, json_path)
            print(f"  Saved {json_path.name} ({len(ann.fields)} fields)")
        elif ann:
            save_annotation(ann, json_path)
            print(f"  Saved {json_path.name} (0 fields)")
        else:
            print(f"  Skipped {img_path.name}")

    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
