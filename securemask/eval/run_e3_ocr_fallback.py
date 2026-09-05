"""E3: OCR engine fallback analysis.

Instruments the OCR call path to determine, per image, which engine was
actually used (EasyOCR primary vs PaddleOCR fallback) and the word count
returned. Reports fallback trigger rate and accuracy split by engine.

Engine ordering (as implemented in ``securemask.core.ocr.OCREngine``):
  - **primary_engine: easyocr** — tried first on every image
  - **fallback_engine: paddleocr** — used when EasyOCR returns too few
    words or low average confidence

Usage::

    python -m securemask.eval.run_e3_ocr_fallback --test-dir <path>
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.eval.annotations_schema import ImageAnnotation, load_test_set
from securemask.eval.metrics import exact_match

logger = logging.getLogger(__name__)


class _OCREngineCapture(logging.Handler):
    """Captures log lines from securemask.core.ocr to detect engine choice."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.engine_used: str | None = None
        self.word_count: int = 0

    def reset(self):
        self.engine_used = None
        self.word_count = 0

    def emit(self, record: logging.LogRecord):
        msg = record.getMessage()
        # EasyOCR accepted as primary
        m = re.search(r"OCR engine: EasyOCR .+ (\d+) words", msg)
        if m:
            self.engine_used = "easyocr"
            self.word_count = int(m.group(1))
            return
        # PaddleOCR used as fallback
        m = re.search(r"OCR engine: PaddleOCR .+ (\d+) words", msg)
        if m:
            self.engine_used = "paddleocr"
            self.word_count = int(m.group(1))
            return
        # EasyOCR retained over PaddleOCR (higher confidence)
        if "retaining higher-confidence EasyOCR" in msg:
            self.engine_used = "easyocr"


def run_ocr_fallback_eval(
    test_set: list[ImageAnnotation],
    output_dir: Path,
) -> dict:
    """Run E3 evaluation and return results dict."""
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

    # Attach log capture to the OCR module logger
    ocr_logger = logging.getLogger("securemask.core.ocr")
    capture = _OCREngineCapture()
    ocr_logger.addHandler(capture)
    ocr_logger.setLevel(logging.DEBUG)

    per_image: list[dict] = []
    engine_counts = {"easyocr": 0, "paddleocr": 0, "unknown": 0}
    engine_correct = {"easyocr": {"correct": 0, "total": 0},
                      "paddleocr": {"correct": 0, "total": 0}}

    total = len(test_set)
    for idx, ann in enumerate(test_set, 1):
        img_path = Path(ann.image_path)
        doc_type = ann.true_document_type
        print(f"  [{idx}/{total}] {img_path.name} ... ", end="", flush=True)

        capture.reset()

        try:
            img_prep_dir = prep_dir / img_path.stem
            variants = save_preprocessed_variants(str(img_path), str(img_prep_dir))
            color_path = str(variants["color"])
            ocr_result = ocr_engine.extract(str(img_path), preprocessed_color_path=color_path)
            pil_img = PILImage.open(img_path).convert("RGB")

            # Classification accuracy
            cls_result = classifier.classify_with_text_fallback(pil_img, ocr_result.full_text)
            cls_correct = cls_result.document_type == doc_type

            # Extraction accuracy (count matching fields)
            detected = extractor.extract(ocr_result, pil_img, doc_type, str(img_path))
            det_map = {d.field_name: d.field_value for d in detected}
            fields_correct = sum(
                1 for f in ann.fields
                if f.field_name in det_map
                and exact_match(det_map[f.field_name], f.true_value, normalize=True)
            )
            fields_total = len(ann.fields)

        except Exception as exc:
            logger.error("E3 failed on %s: %s", img_path.name, exc)
            cls_correct = False
            fields_correct = 0
            fields_total = len(ann.fields)

        engine = capture.engine_used or "unknown"
        word_count = capture.word_count
        engine_counts[engine] = engine_counts.get(engine, 0) + 1

        if engine in engine_correct:
            engine_correct[engine]["total"] += 1
            if cls_correct:
                engine_correct[engine]["correct"] += 1

        print(f"engine={engine}, words={word_count}, cls={'✓' if cls_correct else '✗'}, "
              f"fields={fields_correct}/{fields_total}")

        per_image.append({
            "image": img_path.name,
            "engine_used": engine,
            "word_count": word_count,
            "classification_correct": cls_correct,
            "extraction_fields_correct": fields_correct,
            "extraction_fields_total": fields_total,
        })

    # Cleanup
    ocr_logger.removeHandler(capture)

    # --- Compute summary ---
    n = len(test_set)
    fallback_count = engine_counts.get("paddleocr", 0)
    fallback_rate = fallback_count / max(n, 1)

    engine_accuracy = {}
    for eng in ("easyocr", "paddleocr"):
        ec = engine_correct[eng]
        engine_accuracy[eng] = ec["correct"] / max(ec["total"], 1) if ec["total"] > 0 else None

    # --- Print summary ---
    print(f"\n{'='*60}")
    print(f"E3 OCR Fallback Analysis  (n={n})")
    print(f"{'='*60}")
    print(f"Engine ordering:")
    print(f"  primary_engine:  easyocr")
    print(f"  fallback_engine: paddleocr")
    print(f"\nEngine usage:")
    for eng, count in sorted(engine_counts.items()):
        pct = count / max(n, 1) * 100
        print(f"  {eng:<12}: {count:>4} images ({pct:.1f}%)")
    print(f"\nFallback trigger rate: {fallback_rate:.4f} ({fallback_count}/{n})")
    print(f"\nClassification accuracy by engine:")
    for eng in ("easyocr", "paddleocr"):
        acc = engine_accuracy[eng]
        ec = engine_correct[eng]
        if acc is not None:
            print(f"  {eng:<12}: {acc:.4f} ({ec['correct']}/{ec['total']})")
        else:
            print(f"  {eng:<12}: N/A (0 images used this engine)")

    # --- Save CSV ---
    csv_path = output_dir / "e3_ocr_fallback.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "image", "primary_engine_easyocr_or_fallback_paddleocr",
            "word_count", "classification_correct",
            "extraction_fields_correct", "extraction_fields_total",
        ])
        for row in per_image:
            writer.writerow([
                row["image"], row["engine_used"], row["word_count"],
                row["classification_correct"],
                row["extraction_fields_correct"], row["extraction_fields_total"],
            ])
    print(f"\nSaved: {csv_path}")

    # --- Save JSON ---
    results = {
        "experiment": "E3_ocr_fallback",
        "primary_engine": "easyocr",
        "fallback_engine": "paddleocr",
        "n_images": n,
        "engine_usage_counts": engine_counts,
        "fallback_trigger_rate": round(fallback_rate, 6),
        "classification_accuracy_by_engine": {
            k: round(v, 6) if v is not None else None
            for k, v in engine_accuracy.items()
        },
        "per_image": per_image,
    }
    json_path = output_dir / "e3_results.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {json_path}")

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="E3: OCR engine fallback analysis")
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
    run_ocr_fallback_eval(test_set, output_dir)


if __name__ == "__main__":
    main()
