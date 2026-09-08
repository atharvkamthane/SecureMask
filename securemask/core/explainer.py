"""Explanation generator — method-aware, human-readable explanations for each detected field."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from securemask.models.detected_field import DetectedField


@dataclass
class FieldExplanation:
    """Rich audit explanation linking detection, context, policy necessity, and PEI impact."""
    field_name: str
    detection_method: str
    confidence: float
    necessity: str  # "Required" or "Excess"
    declared_context: str
    recommended_action: str
    recommendation_reason: str
    pei_contribution: float
    decision: str
    summary_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_explanation(field: DetectedField, document_type: str) -> str:
    """Generate a human-readable explanation of how a field was detected."""
    if field.detection_method == "qr":
        return (
            f"{field.field_name} extracted directly from the Aadhaar QR code "
            f"with high confidence. The QR contains digitally signed resident data."
        )

    if field.detection_method == "mrz":
        return (
            f"{field.field_name} decoded from the Machine Readable Zone (MRZ) "
            f"at the bottom of the passport. MRZ lines encode the complete "
            f"identity in a standardised format."
        )

    if field.detection_method == "regex_fuzzy":
        qualifier = "Exact match." if field.confidence > 0.92 else "Approximate match — verify if incorrect."
        return (
            f"{field.field_name} detected because the extracted text "
            f"'{field.field_value[:30]}{'...' if len(field.field_value) > 30 else ''}' "
            f"matches the {document_type} identifier pattern "
            f"(confidence: {field.confidence:.0%}). {qualifier}"
        )

    if field.detection_method == "ner":
        entity_map = {
            "name": "personal name (PER entity)",
            "father_name": "personal name (PER entity)",
            "father_husband_name": "personal name (PER entity)",
            "father_spouse_name": "personal name (PER entity)",
            "address": "location entity (LOC)",
            "place_of_birth": "location entity (LOC)",
        }
        entity_desc = entity_map.get(field.field_name, "named entity")
        return (
            f"{field.field_name} detected as a {entity_desc} by the NER model "
            f"near the keyword anchor. Confidence: {field.confidence:.0%}."
        )

    if field.detection_method == "image":
        return (
            f"{field.field_name} detected as a visual element (QR code / "
            f"signature / photo region) in the document image. "
            f"Always flagged regardless of context."
        )

    return f"{field.field_name} detected in document."


def generate_detailed_field_explanation(
    field: DetectedField,
    document_type: str,
    context: str,
    required: bool,
    pei_contribution: float = 0.0,
) -> FieldExplanation:
    """Construct a full explainability record connecting detection, necessity, recommendation, and PEI."""
    detection_summary = generate_explanation(field, document_type)
    action = getattr(field, "suggested_action", "redact")
    reason = getattr(field, "suggestion_reason", "")
    decision = getattr(field, "redaction_decision", action)

    nec_str = "Required" if required else "Excess"
    ctx_label = context.replace("_", " ")

    summary = (
        f"Field: {field.field_name} | Context: {ctx_label} | Necessity: {nec_str} | "
        f"Recommendation: {action.upper()} ({reason}) | "
        f"PEI impact: {pei_contribution:+.1f} pts. {detection_summary}"
    )

    return FieldExplanation(
        field_name=field.field_name,
        detection_method=field.detection_method,
        confidence=round(float(field.confidence), 2),
        necessity=nec_str,
        declared_context=context,
        recommended_action=action,
        recommendation_reason=reason,
        pei_contribution=round(pei_contribution, 2),
        decision=decision,
        summary_text=summary,
    )
