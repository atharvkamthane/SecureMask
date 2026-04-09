from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "driving licence", "transport department", "licence no",
    "motor vehicles act", "cov", "valid till", "blood group",
]

FIELDS = [
    FieldSchema("dl_number", 9, r"\b[A-Z]{2}[0-9]{2}[A-Z]{0,2}[0-9]{4,7}\b", ["licence no", "dl no", "driving licence", "license number"], "top", regex_description="Indian driving licence number"),
    FieldSchema("name", 5, None, ["name", "holder"], "top", regex_description="person name"),
    FieldSchema("dob", 4, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["dob", "date of birth"], "middle", regex_description="date of birth"),
    FieldSchema("address", 7, None, ["address", "s/o", "w/o", "d/o", "pin"], "bottom", regex_description="address text"),
    FieldSchema("blood_group", 6, r"\b(A|B|AB|O)[+-]\b", ["blood", "bg", "blood group"], "middle", regex_description="blood group marker"),
    FieldSchema("vehicle_class", 2, r"\b(LMV|MCWG|TRANS|HMV|MGV|HTV|PSV)\b", ["class", "vehicle class", "cov"], "middle", regex_description="vehicle class code"),
    FieldSchema("validity", 2, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["valid till", "validity", "expiry", "valid upto"], "bottom", regex_description="validity date"),
]
