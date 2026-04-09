from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
REDACTED_DIR = STORAGE_DIR / "redacted"
DB_PATH = STORAGE_DIR / "securemask.sqlite3"
STATIC_DIR = BASE_DIR / "frontend"

SUPPORTED_CONTEXTS = {
    "age_verification",
    "identity_verification",
    "address_proof",
    "kyc_onboarding",
    "general_upload",
}

SUPPORTED_DOCUMENT_TYPES = {
    "aadhaar",
    "pan",
    "driving_license",
    "passport",
    "voter_id",
    "ration_card",
    "esic",
}


@dataclass(frozen=True)
class FieldSchema:
    field_name: str
    sensitivity_weight: int
    regex: str | None
    keywords: list[str]
    zone: str
    note: str | None = None
    regex_description: str | None = None


UNIVERSAL_REGEX_PATTERNS = {
    "phone": (r"\b(\+91[\-\s]?)?[6-9]\d{9}\b", 6, "Indian mobile phone pattern"),
    "email": (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 6, "email address pattern"),
    "pan_pattern": (r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", 10, "PAN identifier pattern"),
    "aadhaar_pattern": (r"\b\d{4}\s?\d{4}\s?\d{4}\b", 10, "Aadhaar 12-digit identifier pattern"),
    "passport_pattern": (r"\b[A-PR-WY][1-9]\d{7}\b", 10, "Indian passport identifier pattern"),
    "date_pattern": (r"\b(0?[1-9]|[12][0-9]|3[01])[\/\-](0?[1-9]|1[012])[\/\-]\d{4}\b", 4, "date pattern"),
}


def ensure_storage_dirs() -> None:
    for path in (STORAGE_DIR, UPLOAD_DIR, PROCESSED_DIR, REDACTED_DIR):
        path.mkdir(parents=True, exist_ok=True)
