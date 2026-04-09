from __future__ import annotations

from securemask.config import FieldSchema
from securemask.models.detected_field import DetectedField


def explain_field(field: DetectedField, document_type: str, schema: FieldSchema | None = None) -> str:
    regex_description = schema.regex_description if schema else "matching pattern"
    if field.detection_method == "regex":
        return (
            f"{field.field_name} detected because the value '{field.field_value}' matches the "
            f"{document_type} identifier pattern ({regex_description})."
        )
    if field.detection_method == "ner":
        entity_type = field.metadata.get("entity_type", "PII")
        return (
            f"{field.field_name} detected as a {entity_type} entity by the NLP model "
            f"with confidence {field.confidence:.2f}."
        )
    if field.detection_method == "keyword_anchor":
        matched_keyword = field.metadata.get("matched_keyword", "nearby label")
        return f"{field.field_name} detected near the keyword '{matched_keyword}' with value '{field.field_value}'."
    if field.detection_method == "image":
        return f"{field.field_name} detected as a visual element (e.g. QR code, signature region) in the document image."
    return f"{field.field_name} detected as potentially sensitive information."
