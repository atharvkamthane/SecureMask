"""Driving Licence field schema."""
from securemask.schemas.base import FieldSchema

fields = [
    FieldSchema(
        field_name="dl_number",
        sensitivity_weight=9,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b[A-Z]{2}[0-9]{2}[A-Z]{0,2}[0-9]{4,7}\b",
        fuzzy_threshold=75,
        anchor_keywords=["licence no", "dl no", "driving licence",
                         "license number", "dl number"],
        zone="top",
    ),
    FieldSchema(
        field_name="name",
        sensitivity_weight=5,
        extraction_method="ner",
        anchor_keywords=["name", "holder", "s/o", "w/o", "d/o"],
        zone="top",
    ),
    FieldSchema(
        field_name="dob",
        sensitivity_weight=4,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b(0?[1-9]|[12]\d|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b",
        fuzzy_threshold=80,
        anchor_keywords=["dob", "date of birth"],
        zone="middle",
    ),
    FieldSchema(
        field_name="address",
        sensitivity_weight=7,
        extraction_method="ner",
        anchor_keywords=["address", "add.", "pin", "district"],
        zone="bottom",
    ),
    FieldSchema(
        field_name="blood_group",
        sensitivity_weight=6,
        extraction_method="regex_fuzzy",
        regex_pattern=r"\b(A|B|AB|O)[+-]\b",
        fuzzy_threshold=85,
        anchor_keywords=["blood", "bg", "blood group"],
        zone="middle",
    ),
]
