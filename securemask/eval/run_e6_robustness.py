"""E6: Robustness under image degradation.

Applies three degradation types to the clean test set and reruns E1 + E2,
reporting the accuracy delta vs. the clean baseline.

Degradations:
  1. **Skew ±15°** — random rotation via ``cv2.getRotationMatrix2D``
  2. **Reduced brightness** — multiply pixel values by 0.4
  3. **Partial occlusion** — 3–5 random black rectangles (~5–10% of image area each)

**Important**: Degraded images reuse the exact same ground-truth annotations
as the clean baseline (same field values and bboxes). No separate annotation
is required — the degradation is a visual transformation only, and we measure
how well the pipeline recovers the same information from a worse image.

Usage::

    python -m securemask.eval.run_e6_robustness --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.eval.annotations_schema import (
    ImageAnnotation,
    load_test_set,
    save_annotation,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Degradation functions
# ------------------------------------------------------------------

def _apply_skew(img: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """Rotate image by a random angle in [-max_angle, +max_angle]."""
    angle = random.uniform(-max_angle, max_angle)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _apply_reduced_brightness(img: np.ndarray, factor: float = 0.4) -> np.ndarray:
    """Reduce brightness by multiplying pixel values."""
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def _apply_partial_occlusion(img: np.ndarray, n_rects: int | None = None) -> np.ndarray:
    """Draw 3–5 random black rectangles covering ~5–10% of image area each."""
    out = img.copy()
    h, w = out.shape[:2]
    n = n_rects or random.randint(3, 5)
    for _ in range(n):
        rw = random.randint(int(w * 0.08), int(w * 0.18))
        rh = random.randint(int(h * 0.08), int(h * 0.18))
        rx = random.randint(0, max(0, w - rw))
        ry = random.randint(0, max(0, h - rh))
        cv2.rectangle(out, (rx, ry), (rx + rw, ry + rh), (0, 0, 0), -1)
    return out


DEGRADATIONS = {
    "skew_15deg": _apply_skew,
    "reduced_brightness": _apply_reduced_brightness,
    "partial_occlusion": _apply_partial_occlusion,
}


def _create_degraded_set(
    test_set: list[ImageAnnotation],
    degrade_fn,
    output_dir: Path,
) -> list[ImageAnnotation]:
    """Apply a degradation to all images and save with copied annotations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    degraded_set: list[ImageAnnotation] = []

    for ann in test_set:
        img_path = Path(ann.image_path)
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        degraded = degrade_fn(img)
        out_img = output_dir / img_path.name
        cv2.imwrite(str(out_img), degraded)

        # Copy annotation with updated path
        new_ann = ImageAnnotation(
            image_path=str(out_img),
            true_document_type=ann.true_document_type,
            fields=list(ann.fields),  # same GT annotations
        )
        save_annotation(new_ann, out_img.with_suffix(".json"))
        degraded_set.append(new_ann)

    return degraded_set


def _quick_eval(test_set: list[ImageAnnotation], output_dir: Path) -> dict:
    """Run lightweight E1 + E2 and return summary metrics."""
    from securemask.eval.run_e1_classification import run_classification_eval
    from securemask.eval.run_e2_extraction import run_extraction_eval

    e1 = run_classification_eval(test_set, output_dir)
    e2 = run_extraction_eval(test_set, output_dir)

    # Compute average extraction F1 across all fields (normalized mode)
    norm_metrics = e2.get("normalized_metrics", {})
    all_f1 = [m["f1"] for dt in norm_metrics.values() for m in dt.values()]
    avg_f1 = sum(all_f1) / max(len(all_f1), 1) if all_f1 else 0.0

    return {
        "classification_accuracy": e1.get("overall_accuracy", 0.0),
        "extraction_avg_f1": round(avg_f1, 6),
    }


def run_robustness_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
) -> dict:
    """Run E6 evaluation and return results dict."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Clean baseline ---
    print("\n" + "=" * 60)
    print("E6: Running clean baseline ...")
    print("=" * 60)
    clean_dir = output_dir / "clean"
    clean_results = _quick_eval(test_set, clean_dir)

    # --- Degraded runs ---
    degradation_results: dict[str, dict] = {}
    for name, fn in DEGRADATIONS.items():
        print(f"\n{'='*60}")
        print(f"E6: Applying degradation '{name}' ...")
        print(f"{'='*60}")
        deg_img_dir = output_dir / f"degraded_{name}" / "images"
        deg_out_dir = output_dir / f"degraded_{name}" / "results"
        degraded_set = _create_degraded_set(test_set, fn, deg_img_dir)
        if not degraded_set:
            print(f"  No images generated for {name}, skipping.")
            continue
        deg_metrics = _quick_eval(degraded_set, deg_out_dir)
        degradation_results[name] = {
            "degraded": deg_metrics,
            "cls_delta": round(deg_metrics["classification_accuracy"] - clean_results["classification_accuracy"], 6),
            "ext_f1_delta": round(deg_metrics["extraction_avg_f1"] - clean_results["extraction_avg_f1"], 6),
        }

    # --- Summary ---
    print(f"\n{'='*70}")
    print(f"E6 Robustness Results  (n={len(test_set)})")
    print(f"{'='*70}")
    print(f"{'Degradation':<24} {'CleanAcc':>10} {'DegAcc':>10} {'dAcc':>10} {'CleanF1':>10} {'DegF1':>10} {'dF1':>10}")
    print("-" * 84)
    for name, dr in degradation_results.items():
        deg = dr["degraded"]
        print(f"{name:<24} "
              f"{clean_results['classification_accuracy']:>10.4f} "
              f"{deg['classification_accuracy']:>10.4f} "
              f"{dr['cls_delta']:>+10.4f} "
              f"{clean_results['extraction_avg_f1']:>10.4f} "
              f"{deg['extraction_avg_f1']:>10.4f} "
              f"{dr['ext_f1_delta']:>+10.4f}")

    # --- Save outputs ---
    results = {
        "experiment": "E6_robustness",
        "n_images": len(test_set),
        "note": "Degraded images reuse the exact same ground-truth annotations as the clean baseline.",
        "clean_baseline": clean_results,
        "degradations": degradation_results,
    }

    json_path = output_dir / "e6_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {json_path}")

    csv_path = output_dir / "e6_robustness.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["degradation", "clean_cls_accuracy", "degraded_cls_accuracy", "cls_delta",
                          "clean_ext_f1", "degraded_ext_f1", "ext_f1_delta"])
        for name, dr in degradation_results.items():
            deg = dr["degraded"]
            writer.writerow([
                name,
                clean_results["classification_accuracy"],
                deg["classification_accuracy"],
                dr["cls_delta"],
                clean_results["extraction_avg_f1"],
                deg["extraction_avg_f1"],
                dr["ext_f1_delta"],
            ])
    print(f"Saved: {csv_path}")

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="E6: Robustness under degradation")
    parser.add_argument("--test-dir", required=True, type=Path,
                        help="Directory with annotated test images")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: <test-dir>/eval_results)")
    args = parser.parse_args(argv)

    test_set = load_test_set(args.test_dir)
    if not test_set:
        print("No annotated test images found. Exiting.")
        sys.exit(1)

    output_dir = args.output_dir or (args.test_dir / "eval_results")
    run_robustness_eval(test_set, output_dir)


if __name__ == "__main__":
    main()
