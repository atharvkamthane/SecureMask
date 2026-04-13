"""Necessity classifier — full 5-context × 5-document-type matrix."""
from __future__ import annotations

NECESSITY_MATRIX = {
    "aadhaar": {
        "aadhaar_number": {
            "age_verification": False, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "name": {"all": True},
        "dob": {
            "age_verification": True, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "gender": {"all": False},
        "address": {
            "age_verification": False, "identity_verification": False,
            "address_proof": True, "kyc_onboarding": True, "general_upload": False,
        },
        "phone": {"all": False},
        "qr_code": {"all": False},
    },
    "pan": {
        "pan_number": {
            "age_verification": False, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "name": {"all": True},
        "father_name": {"all": False},
        "dob": {
            "age_verification": True, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "signature": {"all": False},
    },
    "passport": {
        "passport_number": {
            "age_verification": False, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "name": {"all": True},
        "dob": {
            "age_verification": True, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "place_of_birth": {"all": False},
        "date_of_expiry": {
            "age_verification": False, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "father_spouse_name": {"all": False},
        "mrz_lines": {"all": False},
    },
    "driving_license": {
        "dl_number": {
            "age_verification": False, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "name": {"all": True},
        "dob": {
            "age_verification": True, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "address": {
            "age_verification": False, "identity_verification": False,
            "address_proof": True, "kyc_onboarding": True, "general_upload": False,
        },
        "blood_group": {"all": False},
    },
    "voter_id": {
        "epic_number": {
            "age_verification": False, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "name": {"all": True},
        "father_husband_name": {"all": False},
        "dob": {
            "age_verification": True, "identity_verification": True,
            "address_proof": False, "kyc_onboarding": True, "general_upload": False,
        },
        "gender": {"all": False},
        "address": {
            "age_verification": False, "identity_verification": False,
            "address_proof": True, "kyc_onboarding": True, "general_upload": False,
        },
    },
}


def check_necessity(document_type: str, field_name: str, context: str) -> bool:
    """Check whether a field is necessary for the declared context.

    Returns True if the field is required, False if excess.
    """
    doc_matrix = NECESSITY_MATRIX.get(document_type, {})
    field_matrix = doc_matrix.get(field_name, {})
    if "all" in field_matrix:
        return field_matrix["all"]
    return field_matrix.get(context, False)
