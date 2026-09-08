"""E1: Document classification evaluation.

Runs the existing MobileNetV2 classifier (with keyword fallback) on each
annotated test image and reports overall accuracy, per-class P/R/F1,
and a confusion matrix.

Usage::

    python -m securemask.eval.run_e1_classification --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

# Suppress OCR pre-warming during evaluation startup
os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.eval.annotations_schema import ImageAnnotation, load_test_set
from securemask.eval.metrics import (
    aggregate_classification_metrics,
    confusion_matrix,
    precision_recall_f1,
)

logger = logging.getLogger(__name__)

LABELS = ["aadhaar", "pan", "passport", "driving_license", "voter_id"]


def run_classification_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
) -> dict:
    """Run E1 evaluation and return results dict."""
    from PIL import Image as PILImage

    from securemask.core.classifier import DocumentClassifier
    from securemask.core.ocr import OCREngine
    from securemask.core.preprocessor import save_preprocessed_variants

    classifier = DocumentClassifier()
    ocr_engine = OCREngine()

    y_true: list[str] = []
    y_pred: list[str] = []
    per_image: list[dict] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    prep_dir = output_dir / "_preprocessed"
    prep_dir.mkdir(parents=True, exist_ok=True)

    total = len(test_set)
    for idx, ann in enumerate(test_set, 1):
        img_path = Path(ann.image_path)
        print(f"  [{idx}/{total}] {img_path.name} ... ", end="", flush=True)

        try:
            # Preprocess
            img_prep_dir = prep_dir / img_path.stem
            variants = save_preprocessed_variants(str(img_path), str(img_prep_dir))
            color_path = str(variants["color"])

            # OCR
            ocr_result = ocr_engine.extract(str(img_path), preprocessed_color_path=color_path)

            # Classify
            pil_img = PILImage.open(img_path).convert("RGB")
            result = classifier.classify_with_text_fallback(pil_img, ocr_result.full_text)
            predicted = result.document_type

        except Exception as exc:
            logger.error("E1 failed on %s: %s", img_path.name, exc)
            predicted = "unknown"

        true_label = ann.true_document_type
        y_true.append(true_label)
        y_pred.append(predicted)
        match = "[OK]" if predicted == true_label else "[X]"
        print(f"{predicted} (true={true_label}) {match}")

        per_image.append({
            "image": img_path.name,
            "true": true_label,
            "predicted": predicted,
            "correct": predicted == true_label,
        })

    # --- Compute metrics ---
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / max(len(y_true), 1)
    per_class = aggregate_classification_metrics(y_true, y_pred, LABELS)
    cm = confusion_matrix(y_true, y_pred, LABELS)

    # --- Print summary ---
    print(f"\n{'='*60}")
    print(f"E1 Classification Results  (n={len(y_true)})")
    print(f"{'='*60}")
    print(f"Overall accuracy: {accuracy:.4f}  ({sum(1 for t,p in zip(y_true,y_pred) if t==p)}/{len(y_true)})")
    print(f"\n{'Class':<20} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 52)
    for label in LABELS:
        m = per_class.get(label, {})
        print(f"{label:<20} {m.get('precision', 0):>10.4f} {m.get('recall', 0):>10.4f} {m.get('f1', 0):>10.4f}")

    print(f"\nConfusion Matrix (rows=true, cols=predicted):")
    header = f"{'':>18}" + "".join(f"{l:>14}" for l in LABELS)
    print(header)
    for true_label in LABELS:
        row = f"{true_label:>18}"
        for pred_label in LABELS:
            row += f"{cm.get(true_label, {}).get(pred_label, 0):>14}"
        print(row)

    # --- Save outputs ---
    results = {
        "experiment": "E1_classification",
        "n_images": len(y_true),
        "overall_accuracy": round(accuracy, 6),
        "per_class": per_class,
        "confusion_matrix": cm,
        "per_image": per_image,
    }

    json_path = output_dir / "e1_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {json_path}")

    # Confusion matrix CSV
    csv_path = output_dir / "e1_confusion_matrix.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["true \\ predicted"] + LABELS)
        for true_label in LABELS:
            row = [true_label] + [cm.get(true_label, {}).get(p, 0) for p in LABELS]
            writer.writerow(row)
    print(f"Saved: {csv_path}")

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="E1: Document classification evaluation")
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
    run_classification_eval(test_set, output_dir)


if __name__ == "__main__":
    main()
