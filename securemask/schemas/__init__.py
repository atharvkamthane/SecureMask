from securemask.schemas import aadhaar, driving_license, esic, pan, passport, ration_card, voter_id


SCHEMA_MODULES = {
    "aadhaar": aadhaar,
    "pan": pan,
    "driving_license": driving_license,
    "passport": passport,
    "voter_id": voter_id,
    "ration_card": ration_card,
    "esic": esic,
}
