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

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

import numpy as np

from securemask.eval.annotations_schema import ImageAnnotation, load_test_set

logger = logging.getLogger(__name__)

MIN_RUNS = 100


def _run_pipeline_once(img_path: str) -> None:
    """Run the full SecureMask pipeline on one image (no return value needed)."""
    from PIL import Image as PILImage

    from securemask.core.classifier import DocumentClassifier
    from securemask.core.extractor import FieldExtractor
    from securemask.core.ocr import OCREngine
    from securemask.core.preprocessor import save_preprocessed_variants
    from securemask.core.redactor import Redactor

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        variants = save_preprocessed_variants(img_path, tmp)
        color_path = str(variants["color"])

        ocr_engine = OCREngine()
        ocr_result = ocr_engine.extract(img_path, preprocessed_color_path=color_path)

        pil_img = PILImage.open(img_path).convert("RGB")
        classifier = DocumentClassifier()
        cls_result = classifier.classify_with_text_fallback(pil_img, ocr_result.full_text)

        extractor = FieldExtractor()
        detected = extractor.extract(ocr_result, pil_img, cls_result.document_type, img_path)

        redactor = Redactor()
        decisions = {f.field_name: "redact" for f in detected}
        redactor.redact(pil_img, detected, decisions)


def _benchmark(image_paths: list[str], device_label: str) -> dict:
    """Run benchmark on a list of image paths and return timing stats."""
    latencies: list[float] = []
    n = len(image_paths)

    for idx, img_path in enumerate(image_paths, 1):
        name = Path(img_path).name
        print(f"  [{idx}/{n}] {name} ... ", end="", flush=True)

        start = time.perf_counter()
        try:
            _run_pipeline_once(img_path)
        except Exception as exc:
            logger.error("Latency run failed on %s: %s", name, exc)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)
        print(f"{elapsed_ms:.0f} ms")

    arr = np.array(latencies)
    return {
        "device": device_label,
        "n_images": n,
        "mean_ms": round(float(np.mean(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "std_ms": round(float(np.std(arr)), 2),
        "latencies_ms": [round(float(x), 2) for x in latencies],
    }


def run_latency_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
) -> dict:
    """Run E7 evaluation and return results dict."""
    import torch

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect image paths, repeat if needed
    image_paths = [ann.image_path for ann in test_set]
    if len(image_paths) < MIN_RUNS:
        repeats = (MIN_RUNS // len(image_paths)) + 1
        image_paths = (image_paths * repeats)[:MIN_RUNS]

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
    args = parser.parse_args(argv)

    test_set = load_test_set(args.test_dir)
    if not test_set:
        print("No annotated test images found. Exiting.")
        sys.exit(1)

    output_dir = args.output_dir or (args.test_dir / "eval_results")
    run_latency_eval(test_set, output_dir)


if __name__ == "__main__":
    main()
