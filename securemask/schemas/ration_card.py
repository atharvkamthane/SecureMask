from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "ration card", "public distribution", "fcs", "nfsa",
    "head of family", "bpl", "apl", "aay",
]

FIELDS = [
    FieldSchema("ration_card_number", 8, r"\b[A-Z]{0,3}[0-9]{8,15}\b", ["ration card no", "card number", "fcs", "nfsa", "ration"], "top", regex_description="ration card number"),
    FieldSchema("head_of_family_name", 5, None, ["head of family", "name", "cardholder"], "top", regex_description="head of family name"),
    FieldSchema("family_members", 6, None, ["member", "family member", "name of member"], "middle", note="multiple person names; flag entire members table region", regex_description="family members table"),
    FieldSchema("address", 7, None, ["address", "village", "district", "taluka", "ward"], "bottom", regex_description="address text"),
    FieldSchema("category", 3, r"\b(APL|BPL|AAY|PHH|NPHH|AY)\b", ["category", "card type", "scheme"], "top", regex_description="ration category"),
    FieldSchema("issue_date", 2, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["issue date", "date of issue"], "bottom", regex_description="issue date"),
]
