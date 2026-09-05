"""E5: Redaction IoU evaluation.

Runs the full pipeline through redaction, then compares the redacted
bounding boxes actually drawn against the ground-truth field boxes using
**Hungarian (optimal) matching** to find the best one-to-one assignment.

Reports mean IoU across all matched pairs plus a per-field breakdown.
Exports 20 random redacted images to a ``review/`` folder for manual
visual inspection of edge leakage.

Usage::

    python -m securemask.eval.run_e5_redaction_iou --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.eval.annotations_schema import ImageAnnotation, load_test_set
from securemask.eval.metrics import compute_iou

logger = logging.getLogger(__name__)


def _hungarian_match_iou(
    gt_boxes: list[list[int]],
    pred_boxes: list[list[int | float]],
) -> list[tuple[int, int, float]]:
    """Match ground-truth boxes to predicted boxes using the Hungarian algorithm.

    Returns list of (gt_index, pred_index, iou) for optimally matched pairs.
    Unmatched entries are excluded.
    """
    from scipy.optimize import linear_sum_assignment

    n_gt = len(gt_boxes)
    n_pred = len(pred_boxes)
    if n_gt == 0 or n_pred == 0:
        return []

    # Build cost matrix (negative IoU for minimisation)
    cost = np.zeros((n_gt, n_pred))
    for i, gt in enumerate(gt_boxes):
        for j, pred in enumerate(pred_boxes):
            cost[i, j] = -compute_iou(gt, pred)

    row_ind, col_ind = linear_sum_assignment(cost)

    matches = []
    for r, c in zip(row_ind, col_ind):
        iou = -cost[r, c]
        if iou > 0:
            matches.append((int(r), int(c), float(iou)))
    return matches


def run_redaction_iou_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
    n_review: int = 20,
) -> dict:
    """Run E5 evaluation and return results dict."""
    from PIL import Image as PILImage

    from securemask.core.classifier import DocumentClassifier
    from securemask.core.extractor import FieldExtractor
    from securemask.core.ocr import OCREngine
    from securemask.core.preprocessor import save_preprocessed_variants
    from securemask.core.redactor import Redactor

    classifier = DocumentClassifier()
    ocr_engine = OCREngine()
    extractor = FieldExtractor()
    redactor = Redactor()

    output_dir.mkdir(parents=True, exist_ok=True)
    review_dir = output_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    prep_dir = output_dir / "_preprocessed"
    prep_dir.mkdir(parents=True, exist_ok=True)

    all_ious: list[float] = []
    per_field_ious: dict[str, list[float]] = defaultdict(list)
    per_image: list[dict] = []

    # Select random review sample
    review_indices = set(random.sample(range(len(test_set)), min(n_review, len(test_set))))

    total = len(test_set)
    for idx, ann in enumerate(test_set, 1):
        img_path = Path(ann.image_path)
        doc_type = ann.true_document_type
        print(f"  [{idx}/{total}] {img_path.name} ... ", end="", flush=True)

        try:
            # Full pipeline
            img_prep_dir = prep_dir / img_path.stem
            variants = save_preprocessed_variants(str(img_path), str(img_prep_dir))
            color_path = str(variants["color"])
            ocr_result = ocr_engine.extract(str(img_path), preprocessed_color_path=color_path)
            pil_img = PILImage.open(img_path).convert("RGB")
            detected = extractor.extract(ocr_result, pil_img, doc_type, str(img_path))

            # Redact all fields
            decisions = {f.field_name: "redact" for f in detected}
            redacted_img = redactor.redact(pil_img, detected, decisions)

            # Collect predicted bboxes (pixel-space)
            pred_boxes = []
            pred_field_names = []
            for d in detected:
                bb = d.bounding_box
                if bb.width > 2 or bb.height > 2:  # skip placeholder bboxes
                    pred_boxes.append([bb.x, bb.y, bb.width, bb.height])
                    pred_field_names.append(d.field_name)

            # Ground-truth bboxes
            gt_boxes = [f.bbox for f in ann.fields]
            gt_field_names = [f.field_name for f in ann.fields]

            # Hungarian matching
            matches = _hungarian_match_iou(gt_boxes, pred_boxes)
            image_ious: list[float] = []
            for gt_i, pred_i, iou in matches:
                all_ious.append(iou)
                image_ious.append(iou)
                per_field_ious[gt_field_names[gt_i]].append(iou)

            mean_iou = sum(image_ious) / max(len(image_ious), 1) if image_ious else 0.0
            print(f"mean_iou={mean_iou:.4f} ({len(matches)} matched)")

            # Save review image
            if (idx - 1) in review_indices:
                review_path = review_dir / f"redacted_{img_path.stem}.png"
                redacted_img.save(str(review_path), "PNG")

            per_image.append({
                "image": img_path.name,
                "doc_type": doc_type,
                "mean_iou": round(mean_iou, 4),
                "n_matched": len(matches),
                "n_gt": len(gt_boxes),
                "n_pred": len(pred_boxes),
            })

        except Exception as exc:
            logger.error("E5 failed on %s: %s", img_path.name, exc)
            per_image.append({
                "image": img_path.name,
                "doc_type": doc_type,
                "mean_iou": 0.0,
                "n_matched": 0,
                "n_gt": len(ann.fields),
                "n_pred": 0,
                "error": str(exc),
            })
            print(f"ERROR: {exc}")

    # --- Summary ---
    overall_mean_iou = sum(all_ious) / max(len(all_ious), 1) if all_ious else 0.0
    field_summary = {
        name: round(sum(vals) / max(len(vals), 1), 6)
        for name, vals in sorted(per_field_ious.items())
    }

    print(f"\n{'='*60}")
    print(f"E5 Redaction IoU Results  (n={len(test_set)})")
    print(f"{'='*60}")
    print(f"Overall mean IoU: {overall_mean_iou:.4f}  ({len(all_ious)} matched pairs)")
    print(f"\nPer-field mean IoU:")
    for name, iou in field_summary.items():
        print(f"  {name:<22}: {iou:.4f}")
    print(f"\nReview images saved to: {review_dir}")

    # --- Save outputs ---
    results = {
        "experiment": "E5_redaction_iou",
        "n_images": len(test_set),
        "overall_mean_iou": round(overall_mean_iou, 6),
        "n_matched_pairs": len(all_ious),
        "per_field_mean_iou": field_summary,
        "review_dir": str(review_dir),
        "per_image": per_image,
    }

    json_path = output_dir / "e5_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {json_path}")

    csv_path = output_dir / "e5_redaction_iou.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "mean_iou", "n_pairs"])
        for name, iou in field_summary.items():
            writer.writerow([name, iou, len(per_field_ious[name])])
    print(f"Saved: {csv_path}")

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="E5: Redaction IoU evaluation")
    parser.add_argument("--test-dir", required=True, type=Path,
                        help="Directory with annotated test images")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: <test-dir>/eval_results)")
    parser.add_argument("--n-review", type=int, default=20,
                        help="Number of random redacted images to save for review")
    args = parser.parse_args(argv)

    test_set = load_test_set(args.test_dir)
    if not test_set:
        print("No annotated test images found. Exiting.")
        sys.exit(1)

    output_dir = args.output_dir or (args.test_dir / "eval_results")
    run_redaction_iou_eval(test_set, output_dir, n_review=args.n_review)


if __name__ == "__main__":
    main()
