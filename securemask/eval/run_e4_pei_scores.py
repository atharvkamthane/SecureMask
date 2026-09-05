"""E4: Calculate Privacy Exposure Index (PEI) scores for the 12 evaluation scenarios.

Calls into existing securemask.core.necessity (check_necessity) and
securemask.core.pei (compute_pei, compute_pei_after_redaction) using real
DetectedField schema definitions.

Output:
  securemask/eval/e4_pei_scores.json: list of 12 {scenario_id, pei_score} entries.

Usage::
    python -m securemask.eval.run_e4_pei_scores
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from securemask.core.necessity import check_necessity
from securemask.core.pei import compute_pei, compute_pei_after_redaction
from securemask.models.detected_field import BoundingBox, DetectedField
from securemask.schemas import get_schema

logger = logging.getLogger(__name__)

SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": "Scenario 1",
        "title": "Age Verification (Aadhaar - Unredacted)",
        "document_type": "aadhaar",
        "declared_context": "age_verification",
        "unredacted_fields": ["name", "dob", "gender", "address", "aadhaar_number", "photo", "name_hi", "father_name", "year_of_birth", "phone", "qr_code"],
        "masked_fields": [],
        "is_unredacted_upload": True,
    },
    {
        "scenario_id": "Scenario 2",
        "title": "Minimal Age Verification (Aadhaar - SecureMask Redacted)",
        "document_type": "aadhaar",
        "declared_context": "age_verification",
        "unredacted_fields": ["dob"],
        "masked_fields": [],
        "is_unredacted_upload": False,
    },
    {
        "scenario_id": "Scenario 3",
        "title": "Identity Verification (PAN Card - Fully Exposed)",
        "document_type": "pan",
        "declared_context": "identity_verification",
        "unredacted_fields": ["name", "father_name", "dob", "pan_number", "photo", "signature", "name_hi"],
        "masked_fields": [],
        "is_unredacted_upload": True,
    },
    {
        "scenario_id": "Scenario 4",
        "title": "Identity Verification (PAN Card - SecureMask Redacted)",
        "document_type": "pan",
        "declared_context": "identity_verification",
        "unredacted_fields": ["name", "pan_number"],
        "masked_fields": [],
        "is_unredacted_upload": False,
    },
    {
        "scenario_id": "Scenario 5",
        "title": "Address Proof (Driving License - Unredacted)",
        "document_type": "driving_license",
        "declared_context": "address_proof",
        "unredacted_fields": ["name", "address", "dl_number", "dob", "blood_group", "photo", "name_hi"],
        "masked_fields": [],
        "is_unredacted_upload": True,
    },
    {
        "scenario_id": "Scenario 6",
        "title": "Address Proof (Driving License - SecureMask Redacted)",
        "document_type": "driving_license",
        "declared_context": "address_proof",
        "unredacted_fields": ["name", "address"],
        "masked_fields": [],
        "is_unredacted_upload": False,
    },
    {
        "scenario_id": "Scenario 7",
        "title": "KYC Onboarding (Passport - Unredacted)",
        "document_type": "passport",
        "declared_context": "kyc_onboarding",
        "unredacted_fields": ["name", "passport_number", "dob", "place_of_birth", "date_of_expiry", "mrz_lines", "photo", "name_hi"],
        "masked_fields": [],
        "is_unredacted_upload": True,
    },
    {
        "scenario_id": "Scenario 8",
        "title": "KYC Onboarding (Passport - Masked Identifier)",
        "document_type": "passport",
        "declared_context": "kyc_onboarding",
        "unredacted_fields": ["name", "date_of_expiry"],
        "masked_fields": ["passport_number"],
        "is_unredacted_upload": False,
    },
    {
        "scenario_id": "Scenario 9",
        "title": "General File Upload (Voter ID - Unredacted)",
        "document_type": "voter_id",
        "declared_context": "general_upload",
        "unredacted_fields": ["name", "epic_number", "father_husband_name", "gender", "dob", "address", "photo", "name_hi"],
        "masked_fields": [],
        "is_unredacted_upload": True,
    },
    {
        "scenario_id": "Scenario 10",
        "title": "General File Upload (Voter ID - SecureMask Redacted)",
        "document_type": "voter_id",
        "declared_context": "general_upload",
        "unredacted_fields": ["name"],
        "masked_fields": [],
        "is_unredacted_upload": False,
    },
    {
        "scenario_id": "Scenario 11",
        "title": "Excess Disclosure (Aadhaar for Address Proof - Unredacted)",
        "document_type": "aadhaar",
        "declared_context": "address_proof",
        "unredacted_fields": ["name", "address", "aadhaar_number", "gender", "dob", "photo", "qr_code", "name_hi", "father_name", "year_of_birth", "phone"],
        "masked_fields": [],
        "is_unredacted_upload": True,
    },
    {
        "scenario_id": "Scenario 12",
        "title": "Minimal Disclosure (Aadhaar for Address Proof - SecureMask Redacted)",
        "document_type": "aadhaar",
        "declared_context": "address_proof",
        "unredacted_fields": ["address"],
        "masked_fields": [],
        "is_unredacted_upload": False,
    },
]


def run_e4_pei_calculation() -> list[dict[str, Any]]:
    """Compute real PEI scores for the 12 scenarios."""
    results: list[dict[str, Any]] = []

    for sc in SCENARIOS:
        doc_type = sc["document_type"]
        context = sc["declared_context"]
        schemas = get_schema(doc_type)

        # Construct real DetectedField objects based on document schema
        detected_fields: list[DetectedField] = [
            DetectedField(
                field_name=s.field_name,
                field_value="SAMPLE_VAL",
                sensitivity_weight=s.sensitivity_weight,
                detection_method=s.extraction_method,
                confidence=0.99,
                bounding_box=BoundingBox(0, 0, 100, 20),
                always_redact=s.always_redact,
            )
            for s in schemas
        ]

        # Determine necessity for each field in the scenario's context
        necessity_results = {
            f.field_name: check_necessity(doc_type, f.field_name, context)
            for f in detected_fields
        }

        if sc["is_unredacted_upload"]:
            # Original unredacted upload: all fields on document are exposed
            pei_score = compute_pei(detected_fields, necessity_results)
        else:
            # Post-redaction state: compute PEI based on decisions
            decisions: dict[str, str] = {}
            for f in detected_fields:
                if f.field_name in sc["unredacted_fields"]:
                    decisions[f.field_name] = "allow"
                elif f.field_name in sc["masked_fields"]:
                    decisions[f.field_name] = "mask"
                else:
                    decisions[f.field_name] = "redact"

            pei_score = compute_pei_after_redaction(
                detected_fields, necessity_results, decisions
            )

        results.append({
            "scenario_id": sc["scenario_id"],
            "title": sc["title"],
            "document_type": doc_type,
            "declared_context": context,
            "pei_score": pei_score,
        })

    return results


def main() -> None:
    results = run_e4_pei_calculation()

    eval_dir = Path(__file__).resolve().parent
    out_json = eval_dir / "e4_pei_scores.json"

    # Simplified list of {scenario_id, pei_score} as required
    simplified_output = [
        {"scenario_id": r["scenario_id"], "pei_score": r["pei_score"]}
        for r in results
    ]

    out_json.write_text(
        json.dumps(simplified_output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Computed PEI scores for 12 scenarios:")
    print("-" * 50)
    for r in results:
        print(f"{r['scenario_id']:<14} {r['title']:<55} PEI: {r['pei_score']:>5.1f}")
    print("-" * 50)
    print(f"Saved: {out_json}")


if __name__ == "__main__":
    main()
