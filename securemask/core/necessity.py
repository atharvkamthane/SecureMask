from __future__ import annotations

from securemask.config import SUPPORTED_CONTEXTS
from securemask.models.detected_field import DetectedField


NECESSITY_MATRIX: dict[str, dict[str, dict[str, bool] | bool]] = {
    "aadhaar": {
        "aadhaar_number": {"age_verification": False, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "name": True,
        "dob": {"age_verification": True, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "gender": False,
        "address": {"age_verification": False, "identity_verification": False, "address_proof": True, "kyc_onboarding": True, "general_upload": False},
        "phone": False,
        "qr_code": False,
    },
    "pan": {
        "pan_number": {"age_verification": False, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "name": True,
        "father_name": False,
        "dob": {"age_verification": True, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "signature": False,
    },
    "driving_license": {
        "dl_number": {"age_verification": False, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "name": True,
        "dob": {"age_verification": True, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "address": {"age_verification": False, "identity_verification": False, "address_proof": True, "kyc_onboarding": True, "general_upload": False},
        "blood_group": False,
        "vehicle_class": False,
        "validity": False,
    },
    "passport": {
        "passport_number": {"age_verification": False, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "name": True,
        "nationality": {"identity_verification": True, "kyc_onboarding": True},
        "dob": {"age_verification": True, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "place_of_birth": False,
        "date_of_issue": False,
        "date_of_expiry": {"identity_verification": True, "kyc_onboarding": True},
        "place_of_issue": False,
        "mrz_line": False,
        "father_name_spouse_name": False,
    },
    "voter_id": {
        "epic_number": {"age_verification": False, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "name": True,
        "father_husband_name": False,
        "dob": {"age_verification": True, "identity_verification": True, "address_proof": False, "kyc_onboarding": True, "general_upload": False},
        "gender": False,
        "address": {"age_verification": False, "identity_verification": False, "address_proof": True, "kyc_onboarding": True, "general_upload": False},
        "assembly_constituency": False,
    },
    "ration_card": {
        "ration_card_number": {"age_verification": False, "identity_verification": True, "address_proof": False, "kyc_onboarding": False, "general_upload": False},
        "head_of_family_name": True,
        "family_members": False,
        "address": {"address_proof": True, "kyc_onboarding": True},
        "category": False,
        "issue_date": False,
    },
    "esic": {
        "insurance_number": {"identity_verification": True, "kyc_onboarding": True},
        "name": True,
        "dob": {"age_verification": True, "identity_verification": True, "kyc_onboarding": True, "general_upload": False},
        "dispensary": False,
        "employer_name": False,
        "family_members": False,
    },
}


def is_required(document_type: str, field_name: str, context: str) -> bool:
    if context not in SUPPORTED_CONTEXTS:
        context = "general_upload"
    rules = NECESSITY_MATRIX.get(document_type, {})
    rule = rules.get(field_name)
    if isinstance(rule, bool):
        return rule
    if isinstance(rule, dict):
        return bool(rule.get(context, False))
    return False


def apply_necessity(document_type: str, context: str, fields: list[DetectedField]) -> list[DetectedField]:
    for field in fields:
        field.required = is_required(document_type, field.field_name, context)
        field.redaction_decision = "allow" if field.required else "redact"
    return fields
