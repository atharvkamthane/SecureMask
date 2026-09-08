"""Run the full evaluation suite and produce a unified results summary.

Runs E1, E2, E3, E5, E6, E7 in sequence against a given test-set folder,
then writes:
  - ``results.json``  — complete structured output
  - ``results_table.csv`` — **Table III** format for the paper

Table III columns:
  document_type | classification_accuracy | extraction_f1 | redaction_iou | mean_latency_ms

If a GPU was available during E7, both CPU and GPU latency numbers are
reported side-by-side in the JSON; the CSV uses CPU latency as the
primary column with an additional ``mean_latency_gpu_ms`` column.

Usage::

    python -m securemask.eval.run_all --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.eval.annotations_schema import load_test_set


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run full SecureMask evaluation suite")
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
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Test set: {len(test_set)} annotated images")
    print(f"Output:   {output_dir}")

    # Import all evaluators
    from securemask.eval.run_e1_classification import run_classification_eval
    from securemask.eval.run_e2_extraction import run_extraction_eval
    from securemask.eval.run_e3_ocr_fallback import run_ocr_fallback_eval
    from securemask.eval.run_e5_redaction_iou import run_redaction_iou_eval
    from securemask.eval.run_e6_robustness import run_robustness_eval
    from securemask.eval.run_e7_latency import run_latency_eval

    # --- E1: Classification ---
    print(f"\n{'#'*60}")
    print(f"# E1: Classification")
    print(f"{'#'*60}")
    e1 = run_classification_eval(test_set, output_dir)

    # --- E2: Extraction ---
    print(f"\n{'#'*60}")
    print(f"# E2: Extraction")
    print(f"{'#'*60}")
    e2 = run_extraction_eval(test_set, output_dir)

    # --- E3: OCR Fallback ---
    print(f"\n{'#'*60}")
    print(f"# E3: OCR Fallback Analysis")
    print(f"{'#'*60}")
    e3 = run_ocr_fallback_eval(test_set, output_dir)

    # --- E5: Redaction IoU ---
    print(f"\n{'#'*60}")
    print(f"# E5: Redaction IoU")
    print(f"{'#'*60}")
    e5 = run_redaction_iou_eval(test_set, output_dir)

    # --- E6: Robustness ---
    print(f"\n{'#'*60}")
    print(f"# E6: Robustness")
    print(f"{'#'*60}")
    e6 = run_robustness_eval(test_set, output_dir)

    # --- E7: Latency ---
    print(f"\n{'#'*60}")
    print(f"# E7: Latency")
    print(f"{'#'*60}")
    e7 = run_latency_eval(test_set, output_dir)

    # ==================================================================
    # Assemble Table III
    # ==================================================================
    doc_types = ["aadhaar", "pan", "passport", "driving_license", "voter_id"]

    # Per-doc-type classification accuracy
    cls_per_type: dict[str, float] = {}
    per_image = e1.get("per_image", [])
    for dt in doc_types:
        images_of_type = [r for r in per_image if r["true"] == dt]
        if images_of_type:
            cls_per_type[dt] = sum(1 for r in images_of_type if r["correct"]) / len(images_of_type)
        else:
            cls_per_type[dt] = 0.0

    # Per-doc-type extraction F1 (average across fields)
    ext_per_type: dict[str, float] = {}
    norm_metrics = e2.get("normalized_metrics", {})
    for dt in doc_types:
        field_metrics = norm_metrics.get(dt, {})
        if field_metrics:
            ext_per_type[dt] = sum(m["f1"] for m in field_metrics.values()) / len(field_metrics)
        else:
            ext_per_type[dt] = 0.0

    # Per-doc-type redaction IoU (average from per-image)
    iou_per_type: dict[str, float] = defaultdict(list)
    for pi in e5.get("per_image", []):
        if pi.get("mean_iou") is not None:
            iou_per_type[pi["doc_type"]].append(pi["mean_iou"])
    iou_avg: dict[str, float] = {}
    for dt in doc_types:
        vals = iou_per_type.get(dt, [])
        iou_avg[dt] = sum(vals) / max(len(vals), 1) if vals else 0.0

    # Latency (global, not per-type)
    cpu_latency = e7.get("cpu", {}).get("mean_ms", 0.0)
    gpu_latency = e7.get("gpu", {}).get("mean_ms", None)

    # --- Print Table III ---
    print(f"\n{'='*80}")
    print(f"TABLE III: SecureMask Evaluation Summary")
    print(f"{'='*80}")
    header = f"{'DocType':<18} {'ClsAcc':>10} {'ExtF1':>10} {'RedactIoU':>10} {'Latency(ms)':>12}"
    if gpu_latency is not None:
        header += f" {'GPU(ms)':>10}"
    print(header)
    print("-" * len(header))
    for dt in doc_types:
        row = (f"{dt:<18} {cls_per_type.get(dt, 0):>10.4f} "
               f"{ext_per_type.get(dt, 0):>10.4f} "
               f"{iou_avg.get(dt, 0):>10.4f} "
               f"{cpu_latency:>12.1f}")
        if gpu_latency is not None:
            row += f" {gpu_latency:>10.1f}"
        print(row)

    # --- Save results.json ---
    results = {
        "experiment": "full_suite",
        "n_images": len(test_set),
        "e1_classification": {
            "overall_accuracy": e1.get("overall_accuracy"),
            "per_class": e1.get("per_class"),
        },
        "e2_extraction": {
            "headline_match_mode": e2.get("headline_match_mode"),
            "headline_avg_f1": e2.get("headline_avg_f1"),
            "per_doc_type_avg_f1": ext_per_type,
        },
        "e3_ocr_fallback": {
            "primary_engine": "easyocr",
            "fallback_engine": "paddleocr",
            "fallback_trigger_rate": e3.get("fallback_trigger_rate"),
        },
        "e5_redaction_iou": {
            "overall_mean_iou": e5.get("overall_mean_iou"),
            "per_doc_type_mean_iou": iou_avg,
        },
        "e6_robustness": e6.get("degradations"),
        "e7_latency": {
            "cpu": e7.get("cpu"),
            "gpu": e7.get("gpu"),
        },
        "table_iii": {
            dt: {
                "classification_accuracy": round(cls_per_type.get(dt, 0), 6),
                "extraction_f1": round(ext_per_type.get(dt, 0), 6),
                "redaction_iou": round(iou_avg.get(dt, 0), 6),
                "mean_latency_cpu_ms": round(cpu_latency, 2),
                "mean_latency_gpu_ms": round(gpu_latency, 2) if gpu_latency else None,
            }
            for dt in doc_types
        },
    }

    json_path = output_dir / "results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {json_path}")

    # --- Save results_table.csv (Table III) ---
    csv_path = output_dir / "results_table.csv"
    csv_columns = ["document_type", "classification_accuracy", "extraction_f1",
                    "redaction_iou", "mean_latency_ms"]
    if gpu_latency is not None:
        csv_columns.append("mean_latency_gpu_ms")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_columns)
        for dt in doc_types:
            row = [
                dt,
                round(cls_per_type.get(dt, 0), 4),
                round(ext_per_type.get(dt, 0), 4),
                round(iou_avg.get(dt, 0), 4),
                round(cpu_latency, 1),
            ]
            if gpu_latency is not None:
                row.append(round(gpu_latency, 1))
            writer.writerow(row)
    print(f"Saved: {csv_path}")

    print(f"\n[SUCCESS] Full evaluation suite complete. Results in {output_dir}/")


if __name__ == "__main__":
    main()
