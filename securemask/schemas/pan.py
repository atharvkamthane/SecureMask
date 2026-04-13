"""PAN card field schema."""
from securemask.schemas.base import FieldSchema

fields = [
    FieldSchema(
        field_name="pan_number",
        sensitivity_weight=10,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        fuzzy_threshold=88,
        anchor_keywords=["permanent account number", "pan", "income tax"],
        zone="middle",
    ),
    FieldSchema(
        field_name="name",
        sensitivity_weight=5,
        extraction_method="ner",
        anchor_keywords=["name"],
        zone="top",
    ),
    FieldSchema(
        field_name="father_name",
        sensitivity_weight=4,
        extraction_method="ner",
        anchor_keywords=["father", "father's name"],
        zone="middle",
    ),
    FieldSchema(
        field_name="dob",
        sensitivity_weight=4,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b",
        fuzzy_threshold=80,
        anchor_keywords=["date of birth", "dob"],
        zone="middle",
    ),
    FieldSchema(
        field_name="signature",
        sensitivity_weight=6,
        extraction_method="image",
        anchor_keywords=["signature"],
        zone="bottom",
        always_redact=True,
    ),
]
