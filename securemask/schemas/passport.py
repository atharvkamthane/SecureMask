"""Passport field schema."""
from securemask.schemas.base import FieldSchema

fields = [
    FieldSchema(
        field_name="passport_number",
        sensitivity_weight=10,
        extraction_method="mrz_primary_regex_fallback",
        regex_pattern=r"\b[A-PR-WY][1-9]\d{7}\b",
        fuzzy_threshold=90,
        anchor_keywords=["passport no", "passport number"],
        zone="top",
    ),
    FieldSchema(
        field_name="name",
        sensitivity_weight=5,
        extraction_method="mrz_primary_ner_fallback",
        anchor_keywords=["surname", "given name"],
        zone="top",
    ),
    FieldSchema(
        field_name="dob",
        sensitivity_weight=4,
        extraction_method="mrz_primary_regex_fallback",
        regex_pattern=r"\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b",
        fuzzy_threshold=80,
        anchor_keywords=["date of birth", "dob"],
        zone="middle",
    ),
    FieldSchema(
        field_name="place_of_birth",
        sensitivity_weight=3,
        extraction_method="ner",
        anchor_keywords=["place of birth", "pob"],
        zone="middle",
    ),
    FieldSchema(
        field_name="date_of_expiry",
        sensitivity_weight=3,
        extraction_method="mrz_primary_regex_fallback",
        regex_pattern=r"\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b",
        fuzzy_threshold=80,
        anchor_keywords=["date of expiry", "expiry", "doe"],
        zone="bottom",
    ),
    FieldSchema(
        field_name="father_spouse_name",
        sensitivity_weight=4,
        extraction_method="ner",
        anchor_keywords=["father", "spouse", "legal guardian"],
        zone="middle",
    ),
    FieldSchema(
        field_name="mrz_lines",
        sensitivity_weight=10,
        extraction_method="mrz",
        regex_pattern=r"[A-Z0-9<]{44}",
        anchor_keywords=[],
        zone="bottom",
        always_redact=True,
    ),
]
