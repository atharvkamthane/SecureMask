from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "election commission", "epic", "elector", "voter",
    "assembly constituency", "parliamentary constituency",
]

FIELDS = [
    FieldSchema("epic_number", 9, r"\b[A-Z]{3}[0-9]{7}\b", ["epic no", "elector", "voter id", "election commission"], "top", regex_description="EPIC voter identifier"),
    FieldSchema("name", 5, None, ["elector's name", "name"], "middle", regex_description="person name"),
    FieldSchema("father_husband_name", 4, None, ["father", "husband", "relation"], "middle", regex_description="relation name"),
    FieldSchema("dob", 4, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["date of birth", "dob", "age"], "middle", regex_description="date of birth"),
    FieldSchema("gender", 2, r"\b(male|female|others)\b", ["gender", "sex"], "middle", regex_description="gender marker"),
    FieldSchema("address", 7, None, ["address", "constituency", "part no", "serial no"], "bottom", regex_description="address text"),
    FieldSchema("assembly_constituency", 3, None, ["assembly constituency", "ac name", "parliamentary"], "bottom", regex_description="constituency name"),
]
