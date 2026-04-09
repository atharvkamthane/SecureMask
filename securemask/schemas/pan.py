from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "permanent account number", "income tax department", "pan",
    "govt of india", "signature",
]

FIELDS = [
    FieldSchema("pan_number", 10, r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", ["permanent account number", "pan", "income tax"], "middle", regex_description="PAN ten-character identifier"),
    FieldSchema("name", 5, None, ["name"], "top", regex_description="person name"),
    FieldSchema("father_name", 4, None, ["father", "father's name"], "middle", regex_description="father's name"),
    FieldSchema("dob", 4, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["date of birth", "dob"], "middle", regex_description="date of birth"),
    FieldSchema("signature", 6, None, ["signature"], "bottom", note="flag the signature region bounding box for masking", regex_description="signature region"),
]
