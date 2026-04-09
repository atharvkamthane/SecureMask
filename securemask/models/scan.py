from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ScanSession:
    scan_id: str
    timestamp: str
    filename: str
    document_type: str
    document_type_confidence: float
    declared_context: str
    original_file_path: str | None
    processable_image_path: str | None
    raw_text: str
    detected_fields: list[dict[str, Any]]
    pei_before: float
    pei_after: float | None = None
    redacted_file_path: str | None = None
    audit_report: dict[str, Any] | None = None
    highlighted_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
