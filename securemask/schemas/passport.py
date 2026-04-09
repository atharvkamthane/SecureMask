from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "republic of india", "passport", "ministry of external affairs",
    "surname", "given name", "nationality", "mrz", "place of birth",
]

FIELDS = [
    FieldSchema("passport_number", 10, r"\b[A-PR-WY][1-9]\d{7}\b", ["passport no", "passport number", "republic of india"], "top", regex_description="Indian passport number"),
    FieldSchema("name", 5, None, ["surname", "given name", "name"], "top", regex_description="person name"),
    FieldSchema("nationality", 2, r"\b(indian|india)\b", ["nationality"], "middle", regex_description="nationality value"),
    FieldSchema("dob", 4, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["date of birth", "dob"], "middle", regex_description="date of birth"),
    FieldSchema("place_of_birth", 3, None, ["place of birth", "pob"], "middle", regex_description="birthplace"),
    FieldSchema("date_of_issue", 3, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["date of issue", "issue date", "doi"], "bottom", regex_description="issue date"),
    FieldSchema("date_of_expiry", 3, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["date of expiry", "expiry", "doe", "valid until"], "bottom", regex_description="expiry date"),
    FieldSchema("place_of_issue", 2, None, ["place of issue", "issued at", "poi"], "bottom", regex_description="place of issue"),
    FieldSchema("mrz_line", 10, r"[A-Z0-9<]{44}", [], "bottom", note="MRZ lines encode full identity data. Always flag.", regex_description="passport MRZ line"),
    FieldSchema("father_name_spouse_name", 4, None, ["father", "spouse", "legal guardian"], "middle", regex_description="father or spouse name"),
]
