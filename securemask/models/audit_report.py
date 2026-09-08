"""Audit report data model with DPDP Act and GDPR compliance notes."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FieldSummary:
    field_name: str
    detected_value_masked: str  # Masked identifier for privacy preservation
    sensitivity_weight: int
    detection_method: str
    confidence: float
    needs_review: bool
    required: bool
    redaction_decision: str
    always_redact: bool
    explanation: str
    redaction_status: str = "applied"
    warning: str | None = None


@dataclass
class ComplianceNotes:
    dpdp_act: str = (
        "Under India's Digital Personal Data Protection Act 2023 (Section 6), "
        "personal data may only be processed for a lawful purpose for which the "
        "data principal has given consent. SecureMask flags fields that exceed "
        "the declared purpose to support data minimisation."
    )
    gdpr_article_5: str = (
        "Under GDPR Article 5(1)(c), personal data must be adequate, relevant, "
        "and limited to what is necessary in relation to the purposes for which "
        "they are processed (data minimisation principle). Fields marked as "
        "'excess' exceed the stated processing intent."
    )


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
    pei_excess_before: float = 0.0
    pei_residual_before: float = 0.0
    pei_excess_after: float = 0.0
    pei_residual_after: float = 0.0
    warnings: list[str] = field(default_factory=list)
    processing_latency_ms: float = 0.0
    fields_detected: list[FieldSummary] = field(default_factory=list)
    compliance_notes: ComplianceNotes = field(default_factory=ComplianceNotes)
    redacted_file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def build(
        cls,
        scan_id: str,
        timestamp: str,
        filename: str,
        document_type: str,
        doc_confidence: float,
        context: str,
        pei_before: float,
        pei_after: float,
        fields: list,
        redacted_path: str = "",
        pei_excess_before: float = 0.0,
        pei_residual_before: float = 0.0,
        pei_excess_after: float = 0.0,
        pei_residual_after: float = 0.0,
        warnings: list[str] | None = None,
        processing_latency_ms: float = 0.0,
    ) -> "AuditReport":
        def _mask(val: str, field_name: str = "") -> str:
            val_clean = str(val).strip()
            if not val_clean or val_clean in ("PHOTO_REGION", "SIGNATURE_REGION", "QR_CODE"):
                return val_clean
            if len(val_clean) <= 4:
                return "****"
            # Mask leading characters, leave trailing 4 visible for verification
            return "*" * (len(val_clean) - 4) + val_clean[-4:]

        field_summaries = [
            FieldSummary(
                field_name=f.field_name,
                detected_value_masked=_mask(f.field_value, f.field_name),
                sensitivity_weight=f.sensitivity_weight,
                detection_method=f.detection_method,
                confidence=round(f.confidence, 2),
                needs_review=f.needs_review,
                required=f.required,
                redaction_decision=f.redaction_decision,
                always_redact=f.always_redact,
                explanation=f.explanation,
                redaction_status=f.metadata.get("redaction_outcome", "applied"),
                warning=f.metadata.get("redaction_warning"),
            )
            for f in fields
        ]
        return cls(
            scan_id=scan_id,
            timestamp=timestamp,
            filename=filename,
            document_type=document_type,
            document_type_confidence=round(doc_confidence, 3),
            declared_context=context,
            pei_before=round(pei_before, 1),
            pei_after=round(pei_after, 1),
            pei_excess_before=round(pei_excess_before, 1),
            pei_residual_before=round(pei_residual_before, 1),
            pei_excess_after=round(pei_excess_after, 1),
            pei_residual_after=round(pei_residual_after, 1),
            warnings=warnings or [],
            processing_latency_ms=round(processing_latency_ms, 2),
            fields_detected=field_summaries,
            redacted_file_path=redacted_path,
        )
