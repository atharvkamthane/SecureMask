"""Explanation generator — method-aware, human-readable explanations for each detected field."""
from __future__ import annotations

from securemask.models.detected_field import DetectedField


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
