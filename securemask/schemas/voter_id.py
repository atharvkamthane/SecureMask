"""Voter ID (EPIC) field schema."""
from securemask.schemas.base import FieldSchema

fields = [
    FieldSchema(
        field_name="epic_number",
        sensitivity_weight=9,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b[A-Z]{3}[0-9]{7}\b",
        fuzzy_threshold=80,
        anchor_keywords=["epic no", "elector", "voter id",
                         "election commission", "epic"],
        zone="top",
    ),
    FieldSchema(
        field_name="name",
        sensitivity_weight=5,
        extraction_method="ner",
        anchor_keywords=["elector's name", "name", "नाम"],
        zone="middle",
    ),
    FieldSchema(
        field_name="father_husband_name",
        sensitivity_weight=4,
        extraction_method="ner",
        anchor_keywords=["father", "husband", "relation", "पिता", "पति"],
        zone="middle",
    ),
    FieldSchema(
        field_name="dob",
        sensitivity_weight=4,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b",
        fuzzy_threshold=80,
        anchor_keywords=["date of birth", "dob", "age", "जन्म"],
        zone="middle",
    ),
    FieldSchema(
        field_name="gender",
        sensitivity_weight=2,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b(male|female|others|पुरुष|महिला)\b",
        fuzzy_threshold=75,
        anchor_keywords=["gender", "sex", "लिंग"],
        zone="middle",
    ),
    FieldSchema(
        field_name="address",
        sensitivity_weight=7,
        extraction_method="ner",
        anchor_keywords=["address", "constituency", "part no", "पता", "विधान सभा"],
        zone="bottom",
    ),
]
