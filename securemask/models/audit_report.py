from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AuditReport:
    scan_id: str
    timestamp: str
    filename: str
    document_type: str
    document_type_confidence: float
    declared_context: str
    pei_before: float
    pei_after: float
    fields_detected: list[dict[str, Any]]
    compliance_notes: dict[str, str]
    redacted_file_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
