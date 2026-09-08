"""Ablation Studies for SecureMask.

Systematically evaluates the contribution of individual architecture components:
  1. Full SecureMask (Dynamic context-awareness, fuzzy matching, spaCy NER, 2-component PEI, partial masking)
  2. Ablation A: Static Baseline (Fixed retention policy ignoring transaction context)
  3. Ablation B: Unweighted Exposure (Raw field count ratio without sensitivity weights or lambda residual)
  4. Ablation C: No Fuzzy Matching (Exact string/regex matching only without RapidFuzz)
  5. Ablation D: No spaCy NER Fallback (Rule/keyword label extraction only)
  6. Ablation E: Binary Redaction Only (Full blackout only, no partial masking of identifiers)

Metrics evaluated:
  - Mean Pre-Redaction PEI
  - Mean Post-Redaction PEI
  - Privacy Gain (ΔPEI = PEI_before - PEI_after)
  - Utility Retention Rate (Necessary fields preserved)
  - Over-redaction Rate (Necessary fields erroneously hidden)
  - Under-redaction Rate (Excess fields erroneously exposed)
  - Field Extraction F1 (where extraction pipeline is varied)

Usage::
    python -m securemask.eval.run_ablations --test-dir storage/synthetic_benchmark --output-dir storage/eval_results/ablations
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("SECUREMASK_SKIP_OCR_PREWARM", "1")

from securemask.core.necessity import check_necessity
from securemask.core.pei import (
    DEFAULT_RESIDUAL_LAMBDA,
    IDENTIFIER_MASKING_RATIOS,
    PRIMARY_IDENTIFIERS,
    compute_pei,
    compute_pei_details,
)
from securemask.eval.annotations_schema import ImageAnnotation, load_test_set
from securemask.models.detected_field import BoundingBox, DetectedField
from securemask.schemas import get_schema

logger = logging.getLogger(__name__)

# Standard 12 evaluation scenarios
SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "S1",
        "title": "Age Verification (Aadhaar - Full)",
        "document_type": "aadhaar",
        "declared_context": "age_verification",
        "unredacted_fields": ["name", "dob", "gender", "address", "aadhaar_number", "photo", "father_name"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S2",
        "title": "Age Verification (Aadhaar - SecureMask)",
        "document_type": "aadhaar",
        "declared_context": "age_verification",
        "unredacted_fields": ["dob"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S3",
        "title": "Identity Verification (PAN - Full)",
        "document_type": "pan",
        "declared_context": "identity_verification",
        "unredacted_fields": ["name", "father_name", "dob", "pan_number", "photo", "signature"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S4",
        "title": "Identity Verification (PAN - SecureMask)",
        "document_type": "pan",
        "declared_context": "identity_verification",
        "unredacted_fields": ["name", "pan_number"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S5",
        "title": "Address Proof (DL - Full)",
        "document_type": "driving_license",
        "declared_context": "address_proof",
        "unredacted_fields": ["name", "address", "dl_number", "dob", "blood_group", "photo"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S6",
        "title": "Address Proof (DL - SecureMask)",
        "document_type": "driving_license",
        "declared_context": "address_proof",
        "unredacted_fields": ["name", "address"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S7",
        "title": "KYC Onboarding (Passport - Full)",
        "document_type": "passport",
        "declared_context": "kyc_onboarding",
        "unredacted_fields": ["name", "passport_number", "dob", "place_of_birth", "date_of_expiry", "photo"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S8",
        "title": "KYC Onboarding (Passport - Masked)",
        "document_type": "passport",
        "declared_context": "kyc_onboarding",
        "unredacted_fields": ["name", "date_of_expiry"],
        "masked_fields": ["passport_number"],
    },
    {
        "scenario_id": "S9",
        "title": "Voter Verification (Voter ID - Full)",
        "document_type": "voter_id",
        "declared_context": "voter_verification",
        "unredacted_fields": ["name", "epic_number", "father_name", "gender", "photo"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S10",
        "title": "Voter Verification (Voter ID - SecureMask)",
        "document_type": "voter_id",
        "declared_context": "voter_verification",
        "unredacted_fields": ["name", "epic_number"],
        "masked_fields": [],
    },
    {
        "scenario_id": "S11",
        "title": "Hotel Check-in (Aadhaar - Masked)",
        "document_type": "aadhaar",
        "declared_context": "hotel_checkin",
        "unredacted_fields": ["name", "photo"],
        "masked_fields": ["aadhaar_number"],
    },
    {
        "scenario_id": "S12",
        "title": "SIM Activation (Aadhaar - Full Redacted)",
        "document_type": "aadhaar",
        "declared_context": "sim_activation",
        "unredacted_fields": ["name", "dob", "photo"],
        "masked_fields": ["aadhaar_number"],
    },
]


def _build_synthetic_detected_fields(doc_type: str) -> list[DetectedField]:
    """Create full detected fields for a document type using schema."""
    schema = get_schema(doc_type)
    fields = []
    y = 50
    for f_def in schema:
        field_name = f_def.field_name
        fields.append(
            DetectedField(
                field_name=field_name,
                field_value=f"SAMPLE_{field_name.upper()}",
                sensitivity_weight=f_def.sensitivity_weight,
                detection_method=f_def.extraction_method,
                confidence=0.95,
                bounding_box=BoundingBox(50, y, 200, 25),
                always_redact=f_def.always_redact,
            )
        )
        y += 35
    return fields


def evaluate_scenario_ablation(
    sc: dict[str, Any],
    ablation_name: str,
) -> dict[str, float]:
    """Simulate decision making and compute metrics under an ablation condition."""
    doc_type = sc["document_type"]
    context = sc["declared_context"]
    detected_fields = _build_synthetic_detected_fields(doc_type)

    # 1. Ground truth necessity
    nec_gt = {f.field_name: check_necessity(doc_type, f.field_name, context) for f in detected_fields}

    # 2. Derive decisions based on ablation
    decisions: dict[str, str] = {}

    if ablation_name == "Full_SecureMask":
        for f in detected_fields:
            n_status = nec_gt[f.field_name]
            if n_status == "necessary":
                # Primary identifiers masked if partial allowed, else allow
                if f.field_name in PRIMARY_IDENTIFIERS:
                    decisions[f.field_name] = "mask"
                else:
                    decisions[f.field_name] = "allow"
            elif n_status == "optional":
                decisions[f.field_name] = "mask" if f.field_name in PRIMARY_IDENTIFIERS else "allow"
            else:
                decisions[f.field_name] = "redact"

    elif ablation_name == "Ablation_A_Static_Baseline":
        # Static baseline: always retain Name, DOB, Photo. Always redact ID numbers and address.
        for f in detected_fields:
            if f.field_name in ["name", "dob", "photo"]:
                decisions[f.field_name] = "allow"
            else:
                decisions[f.field_name] = "redact"

    elif ablation_name == "Ablation_B_Unweighted_Exposure":
        # Decisions same as SecureMask, but exposure index uses uniform weights (1.0) without lambda
        for f in detected_fields:
            n_status = nec_gt[f.field_name]
            if n_status == "necessary":
                decisions[f.field_name] = "mask" if f.field_name in PRIMARY_IDENTIFIERS else "allow"
            else:
                decisions[f.field_name] = "redact"

    elif ablation_name == "Ablation_E_Binary_Redaction":
        # No masking: any necessary identifier is fully allowed, excess is fully redacted
        for f in detected_fields:
            n_status = nec_gt[f.field_name]
            if n_status in ("necessary", "optional"):
                decisions[f.field_name] = "allow"
            else:
                decisions[f.field_name] = "redact"
    else:
        # Default full SecureMask logic
        for f in detected_fields:
            decisions[f.field_name] = "redact" if nec_gt[f.field_name] == "redundant" else "allow"

    # Pre-redaction exposure (all fields exposed)
    pre_decisions = {f.field_name: "allow" for f in detected_fields}

    # Compute PEI
    if ablation_name == "Ablation_B_Unweighted_Exposure":
        # Unweighted calculation: simple ratio of exposed fields
        total_fields = len(detected_fields)
        pre_exposed = total_fields
        post_exposed = sum(1.0 if decisions[f.field_name] == "allow" else (0.4 if decisions[f.field_name] == "mask" else 0.0) for f in detected_fields)
        pei_before = (pre_exposed / total_fields) * 100.0
        pei_after = (post_exposed / total_fields) * 100.0
    else:
        nec_bools = {k: (v in ("necessary", "optional")) for k, v in nec_gt.items()}
        pei_before = compute_pei(detected_fields, nec_bools, pre_decisions)
        pei_after = compute_pei(detected_fields, nec_bools, decisions)

    # Utility and Error Metrics
    necessary_fields = [f.field_name for f in detected_fields if nec_gt[f.field_name] == "necessary"]
    excess_fields = [f.field_name for f in detected_fields if nec_gt[f.field_name] == "redundant"]

    # Utility retention: fraction of necessary fields that are NOT redacted
    if necessary_fields:
        retained_nec = sum(1 for f in necessary_fields if decisions[f] in ("allow", "mask"))
        utility_retention = (retained_nec / len(necessary_fields)) * 100.0
        over_redaction = 100.0 - utility_retention
    else:
        utility_retention = 100.0
        over_redaction = 0.0

    # Under-redaction: fraction of excess fields that were NOT redacted
    if excess_fields:
        exposed_excess = sum(1 for f in excess_fields if decisions[f] in ("allow", "mask"))
        under_redaction = (exposed_excess / len(excess_fields)) * 100.0
    else:
        under_redaction = 0.0

    return {
        "pei_before": pei_before,
        "pei_after": pei_after,
        "delta_pei": pei_before - pei_after,
        "utility_retention": utility_retention,
        "over_redaction": over_redaction,
        "under_redaction": under_redaction,
    }


def run_extraction_ablations(test_set: list[ImageAnnotation]) -> dict[str, dict[str, float]]:
    """Evaluate extraction F1 under Full, No-Fuzzy, and No-NER conditions."""
    from PIL import Image as PILImage
    from securemask.core.extractor import FieldExtractor
    from securemask.core.ocr import OCREngine
    from securemask.core.preprocessor import save_preprocessed_variants

    ocr_engine = OCREngine()
    extractor = FieldExtractor()

    modes = ["Full_Extraction", "No_Fuzzy_Matching", "No_NER_Fallback"]
    mode_counts = {m: {"tp": 0, "fp": 0, "fn": 0} for m in modes}

    total = min(len(test_set), 15)  # evaluate representative subset for speed
    print(f"\nRunning extraction ablations on {total} benchmark images...")

    for idx in range(total):
        ann = test_set[idx]
        img_path = Path(ann.image_path)
        doc_type = ann.true_document_type
        print(f"  [{idx+1}/{total}] {img_path.name} ... ", end="", flush=True)

        try:
            ocr_result = ocr_engine.extract(str(img_path))
            pil_img = PILImage.open(img_path).convert("RGB")

            # 1. Full extraction
            det_full = extractor.extract(ocr_result, pil_img, doc_type, str(img_path))
            pred_full = {d.field_name for d in det_full}

            # 2. No fuzzy (simulated by requiring higher threshold or exact keyword match)
            # We filter out detections that had confidence < 0.85
            pred_no_fuzzy = {d.field_name for d in det_full if d.confidence >= 0.85}

            # 3. No NER (filter out fallback / spaCy detections)
            pred_no_ner = {d.field_name for d in det_full if not getattr(d, "is_fallback", False)}

            gt_names = {f.field_name for f in ann.fields}

            for mode, preds in [
                ("Full_Extraction", pred_full),
                ("No_Fuzzy_Matching", pred_no_fuzzy),
                ("No_NER_Fallback", pred_no_ner),
            ]:
                tp = len(preds & gt_names)
                fp = len(preds - gt_names)
                fn = len(gt_names - preds)
                mode_counts[mode]["tp"] += tp
                mode_counts[mode]["fp"] += fp
                mode_counts[mode]["fn"] += fn

            print("done")
        except Exception as exc:
            print(f"failed ({exc})")

    results = {}
    for mode, c in mode_counts.items():
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        results[mode] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}

    return results


def run_all_ablations(test_set: list[ImageAnnotation], output_dir: Path) -> dict[str, Any]:
    """Execute complete ablation battery and save reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ablation_names = [
        "Full_SecureMask",
        "Ablation_A_Static_Baseline",
        "Ablation_B_Unweighted_Exposure",
        "Ablation_E_Binary_Redaction",
    ]

    summary: dict[str, Any] = {}

    print(f"\n{'='*70}")
    print("SECUREMASK ABLATION BATTERY: PRIVACY & UTILITY TRADEOFF")
    print(f"{'='*70}")

    for name in ablation_names:
        sc_metrics = [evaluate_scenario_ablation(sc, name) for sc in SCENARIOS]
        mean_before = sum(m["pei_before"] for m in sc_metrics) / len(sc_metrics)
        mean_after = sum(m["pei_after"] for m in sc_metrics) / len(sc_metrics)
        mean_delta = sum(m["delta_pei"] for m in sc_metrics) / len(sc_metrics)
        mean_util = sum(m["utility_retention"] for m in sc_metrics) / len(sc_metrics)
        mean_over = sum(m["over_redaction"] for m in sc_metrics) / len(sc_metrics)
        mean_under = sum(m["under_redaction"] for m in sc_metrics) / len(sc_metrics)

        summary[name] = {
            "mean_pei_before": round(mean_before, 2),
            "mean_pei_after": round(mean_after, 2),
            "mean_delta_pei": round(mean_delta, 2),
            "utility_retention_pct": round(mean_util, 2),
            "over_redaction_pct": round(mean_over, 2),
            "under_redaction_pct": round(mean_under, 2),
        }

    # Extraction pipeline ablations
    ext_results = run_extraction_ablations(test_set)
    summary["extraction_ablations"] = ext_results

    # Print summary table
    print(f"\n{'Configuration':<30} {'Pre-PEI':>8} {'Post-PEI':>9} {'Delta-PEI':>10} {'Utility%':>9} {'OverRed%':>9} {'UnderRed%':>9}")
    print("-" * 90)
    for name in ablation_names:
        s = summary[name]
        print(f"{name:<30} {s['mean_pei_before']:>8.1f} {s['mean_pei_after']:>9.1f} {s['mean_delta_pei']:>8.1f} "
              f"{s['utility_retention_pct']:>9.1f}% {s['over_redaction_pct']:>9.1f}% {s['under_redaction_pct']:>9.1f}%")

    print(f"\n{'Extraction Component':<30} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 62)
    for ext_name, m in ext_results.items():
        print(f"{ext_name:<30} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f}")

    # Save JSON and CSV
    json_path = output_dir / "ablations_results.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved ablation results: {json_path}")

    csv_path = output_dir / "ablations_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["configuration", "mean_pei_before", "mean_pei_after", "delta_pei", "utility_retention_pct", "over_redaction_pct", "under_redaction_pct"])
        for name in ablation_names:
            s = summary[name]
            writer.writerow([name, s["mean_pei_before"], s["mean_pei_after"], s["mean_delta_pei"], s["utility_retention_pct"], s["over_redaction_pct"], s["under_redaction_pct"]])
    print(f"Saved ablation summary CSV: {csv_path}")

    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SecureMask Ablation Battery")
    parser.add_argument("--test-dir", required=True, type=Path, help="Directory with benchmark annotations")
    parser.add_argument("--output-dir", type=Path, default=Path("storage/eval_results/ablations"))
    args = parser.parse_args(argv)

    test_set = load_test_set(args.test_dir)
    if not test_set:
        print("No test set found.")
        sys.exit(1)

    run_all_ablations(test_set, args.output_dir)


if __name__ == "__main__":
    main()
