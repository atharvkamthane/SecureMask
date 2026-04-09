from securemask.config import FieldSchema

DOCUMENT_KEYWORDS = [
    "employees state insurance", "esic", "insurance number",
    "insured person", "dispensary", "employer code",
]

FIELDS = [
    FieldSchema("insurance_number", 10, r"\b\d{2}[\/\-]\d{2}[\/\-]\d{6}[\/\-]\d{3}\b", ["insurance number", "esic", "ip number", "insured person"], "top", regex_description="ESIC insurance number"),
    FieldSchema("name", 5, None, ["name", "insured person name"], "top", regex_description="person name"),
    FieldSchema("dob", 4, r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", ["date of birth", "dob"], "middle", regex_description="date of birth"),
    FieldSchema("dispensary", 3, None, ["dispensary", "branch", "local office"], "middle", regex_description="dispensary or branch"),
    FieldSchema("employer_name", 5, None, ["employer", "establishment", "factory"], "middle", regex_description="employer name"),
    FieldSchema("family_members", 6, None, ["family", "dependent", "beneficiary"], "bottom", regex_description="family member details"),
]
