"""Audit report assembler."""
from __future__ import annotations

from securemask.models.audit_report import AuditReport
from securemask.models.detected_field import DetectedField


def generate_audit_report(scan_id: str, timestamp: str, filename: str,
                          document_type: str, doc_confidence: float,
                          context: str, pei_before: float, pei_after: float,
                          fields: list[DetectedField],
                          redacted_path: str = "") -> AuditReport:
    """Build a complete audit report for a scan session."""
    return AuditReport.build(
        scan_id=scan_id,
        timestamp=timestamp,
        filename=filename,
        document_type=document_type,
        doc_confidence=doc_confidence,
        context=context,
        pei_before=pei_before,
        pei_after=pei_after,
        fields=fields,
        redacted_path=redacted_path,
    )
