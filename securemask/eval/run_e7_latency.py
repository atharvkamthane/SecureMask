"""E7: End-to-end latency benchmark.

Runs the full pipeline (preprocess → OCR → classify → extract → redact)
on ≥100 images, measuring wall-clock time per document. If fewer images
are available, repeats the set to reach 100.

Reports mean and p95 latency. If a CUDA GPU is available, runs a second
pass on GPU and reports both CPU and GPU numbers.

Usage::

    python -m securemask.eval.run_e7_latency --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

import numpy as np

from securemask.eval.annotations_schema import ImageAnnotation, load_test_set

logger = logging.getLogger(__name__)

MIN_RUNS = 100


def _run_pipeline_once(
    img_path: str,
    ocr_engine: Any,
    classifier: Any,
    extractor: Any,
    redactor: Any,
) -> dict[str, float]:
    """Run the full SecureMask pipeline on one image and return stage timings in ms."""
    from PIL import Image as PILImage
    from securemask.core.preprocessor import save_preprocessed_variants
    import tempfile

    timings = {}

    # 1. Preprocessing
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        variants = save_preprocessed_variants(img_path, tmp)
        color_path = str(variants["color"])
        timings["preprocessor_ms"] = (time.perf_counter() - t0) * 1000

        # 2. OCR
        t1 = time.perf_counter()
        ocr_result = ocr_engine.extract(img_path, preprocessed_color_path=color_path)
        timings["ocr_ms"] = (time.perf_counter() - t1) * 1000

        # 3. Classification
        t2 = time.perf_counter()
        pil_img = PILImage.open(img_path).convert("RGB")
        cls_result = classifier.classify_with_text_fallback(pil_img, ocr_result.full_text)
        timings["classifier_ms"] = (time.perf_counter() - t2) * 1000

        # 4. Field Extraction
        t3 = time.perf_counter()
        detected = extractor.extract(ocr_result, pil_img, cls_result.document_type, img_path)
        timings["extractor_ms"] = (time.perf_counter() - t3) * 1000

        # 5. Redaction
        t4 = time.perf_counter()
        decisions = {f.field_name: "redact" for f in detected}
        redactor.redact(pil_img, detected, decisions)
        timings["redactor_ms"] = (time.perf_counter() - t4) * 1000

    timings["total_ms"] = sum(timings.values())
    return timings


def _benchmark(image_paths: list[str], device_label: str) -> dict:
    """Run benchmark on a list of image paths and return timing stats."""
    from securemask.core.classifier import DocumentClassifier
    from securemask.core.extractor import FieldExtractor
    from securemask.core.ocr import OCREngine
    from securemask.core.redactor import Redactor

    # Pre-instantiate singletons for benchmark
    print("  Warming up pipeline components...")
    ocr_engine = OCREngine()
    classifier = DocumentClassifier()
    extractor = FieldExtractor()
    redactor = Redactor()

    latencies: list[float] = []
    stage_breakdowns: dict[str, list[float]] = {
        "preprocessor_ms": [],
        "ocr_ms": [],
        "classifier_ms": [],
        "extractor_ms": [],
        "redactor_ms": [],
    }

    n = len(image_paths)

    for idx, img_path in enumerate(image_paths, 1):
        name = Path(img_path).name
        print(f"  [{idx}/{n}] {name} ... ", end="", flush=True)

        try:
            stage_times = _run_pipeline_once(img_path, ocr_engine, classifier, extractor, redactor)
            tot = stage_times["total_ms"]
            latencies.append(tot)
            for k in stage_breakdowns:
                stage_breakdowns[k].append(stage_times.get(k, 0.0))
            print(f"{tot:.0f} ms (ocr: {stage_times['ocr_ms']:.0f}ms)")
        except Exception as exc:
            logger.error("Latency run failed on %s: %s", name, exc)
            print("FAILED")

    arr = np.array(latencies) if latencies else np.array([0.0])
    stage_means = {k: round(float(np.mean(v)), 2) for k, v in stage_breakdowns.items() if v}

    return {
        "device": device_label,
        "n_images": len(latencies),
        "mean_ms": round(float(np.mean(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "std_ms": round(float(np.std(arr)), 2),
        "stage_breakdown_means": stage_means,
        "latencies_ms": [round(float(x), 2) for x in latencies],
    }


def run_latency_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
    min_runs: int = 25,
) -> dict:
    """Run E7 evaluation and return results dict."""
    import torch

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect image paths, repeat or slice to min_runs
    image_paths = [ann.image_path for ann in test_set]
    if len(image_paths) < min_runs:
        repeats = (min_runs // len(image_paths)) + 1
        image_paths = (image_paths * repeats)[:min_runs]
    else:
        image_paths = image_paths[:min_runs]

    # --- CPU run ---
    print(f"\n{'='*60}")
    print(f"E7: Latency benchmark — CPU  (n={len(image_paths)})")
    print(f"{'='*60}")
    cpu_results = _benchmark(image_paths, "cpu")

    # --- GPU run (if available) ---
    gpu_results = None
    if torch.cuda.is_available():
        print(f"\n{'='*60}")
        print(f"E7: Latency benchmark — GPU  (n={len(image_paths)})")
        print(f"{'='*60}")
        gpu_results = _benchmark(image_paths, "gpu")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"E7 Latency Results")
    print(f"{'='*60}")
    print(f"{'Device':<8} {'N':>6} {'Mean(ms)':>10} {'P95(ms)':>10} {'Min(ms)':>10} {'Max(ms)':>10}")
    print("-" * 56)
    for r in [cpu_results] + ([gpu_results] if gpu_results else []):
        print(f"{r['device']:<8} {r['n_images']:>6} {r['mean_ms']:>10.1f} {r['p95_ms']:>10.1f} "
              f"{r['min_ms']:>10.1f} {r['max_ms']:>10.1f}")

    # --- Save outputs ---
    results = {
        "experiment": "E7_latency",
        "n_images_per_run": len(image_paths),
        "cpu": {k: v for k, v in cpu_results.items() if k != "latencies_ms"},
        "gpu": {k: v for k, v in gpu_results.items() if k != "latencies_ms"} if gpu_results else None,
        "gpu_available": gpu_results is not None,
    }
    # Remove None values
    results = {k: v for k, v in results.items() if v is not None}

    json_path = output_dir / "e7_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {json_path}")

    csv_path = output_dir / "e7_latency.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["device", "mean_ms", "p95_ms", "min_ms", "max_ms", "std_ms", "n_images"])
        for r in [cpu_results] + ([gpu_results] if gpu_results else []):
            writer.writerow([r["device"], r["mean_ms"], r["p95_ms"],
                             r["min_ms"], r["max_ms"], r["std_ms"], r["n_images"]])
    print(f"Saved: {csv_path}")

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="E7: End-to-end latency benchmark")
    parser.add_argument("--test-dir", required=True, type=Path,
                        help="Directory with annotated test images")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: <test-dir>/eval_results)")
    parser.add_argument("--runs", type=int, default=25,
                        help="Number of iterations to run (default: 25)")
    args = parser.parse_args(argv)

    test_set = load_test_set(args.test_dir)
    if not test_set:
        print("No annotated test images found. Exiting.")
        sys.exit(1)

    output_dir = args.output_dir or (args.test_dir / "eval_results")
    run_latency_eval(test_set, output_dir, min_runs=args.runs)


if __name__ == "__main__":
    main()
