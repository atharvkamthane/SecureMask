"""Context-aware redaction recommendations."""
from __future__ import annotations

from dataclasses import dataclass

from securemask.models.detected_field import DetectedField


from securemask.config import IDENTIFIER_FIELDS

VISUAL_SECRET_FIELDS = {"photo", "signature", "qr_code", "mrz_lines"}
AGE_FIELDS = {"dob", "date_of_birth"}


@dataclass(frozen=True)
class Recommendation:
    action: str
    reason: str


def recommend_action(field: DetectedField, document_type: str, context: str, required: bool) -> Recommendation:
    """Return the safest default user action for a field.

    Actions intentionally stay within the existing UI contract:
    ``allow``, ``mask``, or ``redact``.
    """
    name = field.field_name

    if field.always_redact or name in VISUAL_SECRET_FIELDS:
        return Recommendation(
            "redact",
            "Remove this visual or machine-readable region because it can expose the full identity even when text fields are hidden.",
        )

    if name in IDENTIFIER_FIELDS:
        if required and context in {"identity_verification", "kyc_onboarding"}:
            return Recommendation(
                "mask",
                "Keep only enough of the identifier visible for verification and hide the rest to reduce replay or fraud risk.",
            )
        return Recommendation(
            "redact",
            "This identifier is not necessary for the selected purpose, so the safest option is to remove it.",
        )

    if name in AGE_FIELDS and context == "age_verification":
        return Recommendation(
            "mask",
            "Age checks usually need proof of age, not the complete date of birth, so partial masking is safer.",
        )

    if required:
        return Recommendation(
            "allow",
            f"This field is needed for {context.replace('_', ' ')} on a {document_type.replace('_', ' ')} document.",
        )

    return Recommendation(
        "redact",
        f"This field is excess for {context.replace('_', ' ')}, so redaction follows data minimisation.",
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
