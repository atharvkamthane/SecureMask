from __future__ import annotations

from datetime import datetime, timezone

from securemask.models.audit_report import AuditReport
from securemask.models.detected_field import DetectedField


def value_preview(value: str, sensitive: bool = True) -> str:
    if not value:
        return ""
    if not sensitive:
        return value
    return f"{value[:4]}****"


def build_audit_report(
    scan_id: str,
    timestamp: str | None,
    filename: str,
    document_type: str,
    document_type_confidence: float,
    declared_context: str,
    pei_before: float,
    pei_after: float,
    fields: list[DetectedField],
    redacted_file_path: str,
) -> AuditReport:
    redacted = [field.field_name for field in fields if field.redaction_decision != "allow"]
    dpdp_note = "Data minimization principle applied"
    if redacted:
        dpdp_note = f"Fields {', '.join(redacted)} redacted per Section 4 data minimization."
    gdpr_note = "Compliant" if redacted or pei_after <= pei_before else "Review redaction choices; exposure increased."
    return AuditReport(
        scan_id=scan_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        filename=filename,
        document_type=document_type,
        document_type_confidence=document_type_confidence,
        declared_context=declared_context,
        pei_before=pei_before,
        pei_after=pei_after,
        fields_detected=[
            {
                "field_name": field.field_name,
                "value_preview": value_preview(field.field_value),
                "sensitivity_weight": field.sensitivity_weight,
                "required": field.required,
                "redaction_decision": field.redaction_decision,
                "detection_method": field.detection_method,
                "explanation": field.explanation,
            }
            for field in fields
        ],
        compliance_notes={"dpdp_act": dpdp_note, "gdpr_article_5": gdpr_note},
        redacted_file_path=redacted_file_path,
    )
