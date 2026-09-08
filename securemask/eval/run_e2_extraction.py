"""E2: Field extraction evaluation.

Runs the extraction pipeline on each annotated test image and compares
extracted fields against ground truth.

Reports both **normalized** and **strict** exact-match modes. The headline
number in ``e2_results.json`` uses normalized matching (whitespace-stripped,
case-insensitive). If results differ meaningfully, both are included so the
paper's methodology section is unambiguous.

Output CSV columns (paper-ready):
  document_type, field, precision, recall, f1

Usage::

    python -m securemask.eval.run_e2_extraction --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.eval.annotations_schema import ImageAnnotation, load_test_set
from securemask.eval.metrics import compute_iou, exact_match, precision_recall_f1

logger = logging.getLogger(__name__)

IOU_THRESHOLD = 0.5


def run_extraction_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
) -> dict:
    """Run E2 evaluation and return results dict."""
    from PIL import Image as PILImage

    from securemask.core.classifier import DocumentClassifier
    from securemask.core.extractor import FieldExtractor
    from securemask.core.ocr import OCREngine
    from securemask.core.preprocessor import save_preprocessed_variants

    classifier = DocumentClassifier()
    ocr_engine = OCREngine()
    extractor = FieldExtractor()

    output_dir.mkdir(parents=True, exist_ok=True)
    prep_dir = output_dir / "_preprocessed"
    prep_dir.mkdir(parents=True, exist_ok=True)

    # Counters: (doc_type, field_name) → {tp, fp, fn} for normalized and strict
    norm_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    strict_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    bbox_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"match": 0, "total": 0})

    per_image: list[dict] = []
    total = len(test_set)

    for idx, ann in enumerate(test_set, 1):
        img_path = Path(ann.image_path)
        doc_type = ann.true_document_type
        print(f"  [{idx}/{total}] {img_path.name} ({doc_type}) ... ", end="", flush=True)

        try:
            # Pipeline: preprocess → OCR → classify → extract
            img_prep_dir = prep_dir / img_path.stem
            variants = save_preprocessed_variants(str(img_path), str(img_prep_dir))
            color_path = str(variants["color"])
            ocr_result = ocr_engine.extract(str(img_path), preprocessed_color_path=color_path)
            pil_img = PILImage.open(img_path).convert("RGB")

            # Use ground-truth doc type for extraction (isolates extraction eval from classification)
            detected = extractor.extract(ocr_result, pil_img, doc_type, str(img_path))
        except Exception as exc:
            logger.error("E2 failed on %s: %s", img_path.name, exc)
            detected = []

        # Build lookup: field_name → DetectedField
        detected_map: dict[str, object] = {}
        for d in detected:
            if d.field_name not in detected_map:
                detected_map[d.field_name] = d

        gt_fields = {f.field_name for f in ann.fields}
        pred_fields = set(detected_map.keys())
        image_results: list[dict] = []

        for gt_field in ann.fields:
            key = (doc_type, gt_field.field_name)
            if gt_field.field_name in detected_map:
                det = detected_map[gt_field.field_name]
                # Normalized match
                if exact_match(det.field_value, gt_field.true_value, normalize=True):
                    norm_counts[key]["tp"] += 1
                else:
                    norm_counts[key]["fp"] += 1
                    norm_counts[key]["fn"] += 1

                # Strict match
                if exact_match(det.field_value, gt_field.true_value, normalize=False):
                    strict_counts[key]["tp"] += 1
                else:
                    strict_counts[key]["fp"] += 1
                    strict_counts[key]["fn"] += 1

                # BBox IoU match
                det_bbox = [det.bounding_box.x, det.bounding_box.y,
                            det.bounding_box.width, det.bounding_box.height]
                iou = compute_iou(det_bbox, gt_field.bbox)
                bbox_counts[key]["total"] += 1
                if iou >= IOU_THRESHOLD:
                    bbox_counts[key]["match"] += 1

                image_results.append({
                    "field": gt_field.field_name,
                    "gt_value": gt_field.true_value,
                    "pred_value": det.field_value,
                    "norm_match": exact_match(det.field_value, gt_field.true_value, normalize=True),
                    "strict_match": exact_match(det.field_value, gt_field.true_value, normalize=False),
                    "iou": round(iou, 4),
                })
            else:
                # Missed field
                norm_counts[key]["fn"] += 1
                strict_counts[key]["fn"] += 1
                image_results.append({
                    "field": gt_field.field_name,
                    "gt_value": gt_field.true_value,
                    "pred_value": None,
                    "norm_match": False,
                    "strict_match": False,
                    "iou": 0.0,
                })

        # Spurious detections (predicted but not in GT)
        for pred_name in pred_fields - gt_fields:
            key = (doc_type, pred_name)
            norm_counts[key]["fp"] += 1
            strict_counts[key]["fp"] += 1

        matches = sum(1 for r in image_results if r["norm_match"])
        print(f"{matches}/{len(ann.fields)} fields matched")

        per_image.append({
            "image": img_path.name,
            "doc_type": doc_type,
            "fields": image_results,
        })

    # --- Aggregate per (doc_type, field) ---
    all_keys = sorted(set(list(norm_counts.keys()) + list(strict_counts.keys())))

    norm_metrics: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    strict_metrics: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    bbox_metrics: dict[str, dict[str, float]] = defaultdict(dict)

    for key in all_keys:
        doc_type, field_name = key
        nc = norm_counts[key]
        p, r, f = precision_recall_f1(nc["tp"], nc["fp"], nc["fn"])
        norm_metrics[doc_type][field_name] = {"precision": p, "recall": r, "f1": f}

        sc = strict_counts[key]
        p2, r2, f2 = precision_recall_f1(sc["tp"], sc["fp"], sc["fn"])
        strict_metrics[doc_type][field_name] = {"precision": p2, "recall": r2, "f1": f2}

        bc = bbox_counts[key]
        bbox_metrics[doc_type][field_name] = bc["match"] / max(bc["total"], 1) if bc["total"] > 0 else 0.0

    # Check if normalized vs strict differ meaningfully
    norm_f1s = [m["f1"] for dt in norm_metrics.values() for m in dt.values()]
    strict_f1s = [m["f1"] for dt in strict_metrics.values() for m in dt.values()]
    avg_norm = sum(norm_f1s) / max(len(norm_f1s), 1)
    avg_strict = sum(strict_f1s) / max(len(strict_f1s), 1)
    modes_differ = abs(avg_norm - avg_strict) > 0.01

    # --- Print summary ---
    print(f"\n{'='*70}")
    print(f"E2 Extraction Results  (n={len(test_set)})")
    print(f"{'='*70}")
    print(f"Headline match mode: normalized (whitespace-stripped, case-insensitive)")
    print(f"Average F1 (normalized): {avg_norm:.4f}")
    if modes_differ:
        print(f"Average F1 (strict):     {avg_strict:.4f}  <- differs from normalized")

    print(f"\n{'DocType':<18} {'Field':<22} {'Prec':>8} {'Rec':>8} {'F1':>8} {'BBoxIoU':>8}")
    print("-" * 74)
    for doc_type in sorted(norm_metrics.keys()):
        for field_name in sorted(norm_metrics[doc_type].keys()):
            m = norm_metrics[doc_type][field_name]
            bb = bbox_metrics.get(doc_type, {}).get(field_name, 0.0)
            print(f"{doc_type:<18} {field_name:<22} {m['precision']:>8.4f} {m['recall']:>8.4f} {m['f1']:>8.4f} {bb:>8.4f}")

    # --- Save CSV (paper-ready) ---
    csv_path = output_dir / "e2_extraction.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["document_type", "field", "precision", "recall", "f1"])
        for doc_type in sorted(norm_metrics.keys()):
            for field_name in sorted(norm_metrics[doc_type].keys()):
                m = norm_metrics[doc_type][field_name]
                writer.writerow([doc_type, field_name, m["precision"], m["recall"], m["f1"]])
    print(f"\nSaved: {csv_path}")

    # --- Save JSON ---
    results = {
        "experiment": "E2_extraction",
        "n_images": len(test_set),
        "headline_match_mode": "normalized",
        "headline_avg_f1": round(avg_norm, 6),
        "normalized_metrics": {k: dict(v) for k, v in norm_metrics.items()},
        "strict_metrics": {k: dict(v) for k, v in strict_metrics.items()} if modes_differ else None,
        "strict_avg_f1": round(avg_strict, 6) if modes_differ else None,
        "modes_differ_meaningfully": modes_differ,
        "bbox_iou_match_rate": {k: dict(v) for k, v in bbox_metrics.items()},
        "iou_threshold": IOU_THRESHOLD,
        "per_image": per_image,
    }
    # Strip None values
    results = {k: v for k, v in results.items() if v is not None}

    json_path = output_dir / "e2_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {json_path}")

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="E2: Field extraction evaluation")
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
    run_extraction_eval(test_set, output_dir)


if __name__ == "__main__":
    main()
