from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "aadhaar", "uid", "uidai", "unique identification authority",
    "government of india", "आधार", "नाम", "पता",
]

FIELDS = [
    FieldSchema("aadhaar_number", 10, r"\b\d{4}\s?\d{4}\s?\d{4}\b", ["aadhaar", "uid", "unique identification"], "middle", regex_description="Aadhaar 12-digit number"),
    FieldSchema("name", 5, None, ["name", "नाम"], "top", regex_description="person name"),
    FieldSchema("dob", 4, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["dob", "date of birth", "जन्म तिथि"], "middle", regex_description="date of birth"),
    FieldSchema("gender", 2, r"\b(male|female|transgender|पुरुष|महिला)\b", ["gender", "sex", "लिंग"], "middle", regex_description="gender marker"),
    FieldSchema("address", 7, None, ["address", "पता", "s/o", "w/o", "d/o", "house", "village", "district", "state", "pin"], "bottom", regex_description="address text"),
    FieldSchema("phone", 6, r"\b(\+91[\-\s]?)?[6-9]\d{9}\b", ["mobile", "phone", "contact"], "anywhere", regex_description="Indian mobile number"),
    FieldSchema("qr_code", 9, None, [], "bottom", note="detect QR code presence using image processing, flag for masking", regex_description="QR code"),
]
