"""Audit report assembler."""
from __future__ import annotations

from securemask.models.audit_report import AuditReport
from securemask.models.detected_field import DetectedField


def generate_audit_report(
    scan_id: str,
    timestamp: str,
    filename: str,
    document_type: str,
    doc_confidence: float,
    context: str,
    pei_before: float,
    pei_after: float,
    fields: list[DetectedField],
    redacted_path: str = "",
    pei_excess_before: float = 0.0,
    pei_residual_before: float = 0.0,
    pei_excess_after: float = 0.0,
    pei_residual_after: float = 0.0,
    warnings: list[str] | None = None,
    processing_latency_ms: float = 0.0,
) -> AuditReport:
    """Build a complete, reproducible audit report for a scan session."""
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
        pei_excess_before=pei_excess_before,
        pei_residual_before=pei_residual_before,
        pei_excess_after=pei_excess_after,
        pei_residual_after=pei_residual_after,
        warnings=warnings,
        processing_latency_ms=processing_latency_ms,
    )
