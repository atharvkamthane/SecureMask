"""Context-aware redaction recommendations."""
from __future__ import annotations

from dataclasses import dataclass

from securemask.models.detected_field import DetectedField


from securemask.config import IDENTIFIER_FIELDS

VISUAL_SECRET_FIELDS = {"photo", "signature", "qr_code", "mrz_lines"}
AGE_FIELDS = {"dob", "date_of_birth"}
NAME_FIELDS = {"name", "name_hi"}


@dataclass(frozen=True)
class Recommendation:
    action: str
    reason: str


# Human-readable field labels for better suggestion text
_FIELD_LABELS = {
    "aadhaar_number": "Aadhaar number",
    "pan_number": "PAN number",
    "passport_number": "passport number",
    "dl_number": "driving licence number",
    "epic_number": "voter ID number",
    "name": "name (English)",
    "name_hi": "name (Hindi/Devanagari)",
    "dob": "date of birth",
    "gender": "gender",
    "address": "address",
    "phone": "phone number",
    "photo": "photograph",
    "signature": "signature",
    "qr_code": "QR code",
    "mrz_lines": "machine-readable zone",
    "father_name": "father's name",
    "father_husband_name": "father/husband's name",
    "father_spouse_name": "father/spouse's name",
    "place_of_birth": "place of birth",
    "date_of_expiry": "expiry date",
    "blood_group": "blood group",
}


def _field_label(field_name: str) -> str:
    return _FIELD_LABELS.get(field_name, field_name.replace("_", " "))


def recommend_action(field: DetectedField, document_type: str, context: str, required: bool) -> Recommendation:
    """Return the safest default user action for a field.

    Actions intentionally stay within the existing UI contract:
    ``allow``, ``mask``, or ``redact``.
    """
    name = field.field_name
    label = _field_label(name)
    ctx_label = context.replace("_", " ")
    doc_label = document_type.replace("_", " ")

    if field.always_redact or name in VISUAL_SECRET_FIELDS:
        return Recommendation(
            "redact",
            f"The {label} is a visual element that can expose full identity even when text fields are hidden. Always removed for safety.",
        )

    if name in IDENTIFIER_FIELDS:
        if required and context in {"identity_verification", "kyc_onboarding"}:
            return Recommendation(
                "mask",
                f"The {label} is needed for {ctx_label}, but showing only the last few digits reduces fraud and replay risk.",
            )
        return Recommendation(
            "redact",
            f"The {label} is not required for {ctx_label}. Removing it follows data minimisation best practice.",
        )

    if name in AGE_FIELDS and context == "age_verification":
        return Recommendation(
            "mask",
            f"Only proof of age is needed, not the full {label}. Partial masking reveals enough while limiting exposure.",
        )

    if name in NAME_FIELDS and required:
        return Recommendation(
            "allow",
            f"The {label} is required to confirm identity for {ctx_label} on this {doc_label} document.",
        )

    if required:
        return Recommendation(
            "allow",
            f"The {label} is needed for {ctx_label} on a {doc_label} document.",
        )

    return Recommendation(
        "redact",
        f"The {label} is not required for {ctx_label}. Redacting it reduces unnecessary data exposure.",
    )


def summarize_recommendations(fields: list[DetectedField]) -> dict[str, int | str]:
    counts = {"allow": 0, "mask": 0, "redact": 0}
    for field in fields:
        action = field.suggested_action if field.suggested_action in counts else "redact"
        counts[action] += 1

    return {
        **counts,
        "summary": (
            f"Recommended defaults: allow {counts['allow']} required fields, "
            f"mask {counts['mask']} verification fields, redact {counts['redact']} excess or high-risk fields."
        ),
    }
