"""Schema registry — maps document types to their field schemas."""
from __future__ import annotations

from securemask.schemas.base import FieldSchema


def get_schema(document_type: str) -> list[FieldSchema]:
    """Return the field schema list for a given document type."""
    if document_type == "aadhaar":
        from securemask.schemas.aadhaar import fields
        return fields
    elif document_type == "pan":
        from securemask.schemas.pan import fields
        return fields
    elif document_type == "passport":
        from securemask.schemas.passport import fields
        return fields
    elif document_type == "driving_license":
        from securemask.schemas.driving_license import fields
        return fields
    elif document_type == "voter_id":
        from securemask.schemas.voter_id import fields
        return fields
    else:
        return []
