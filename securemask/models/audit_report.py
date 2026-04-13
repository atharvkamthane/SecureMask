"""Audit report data model with DPDP Act and GDPR compliance notes."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FieldSummary:
    field_name: str
    detected_value_masked: str  # first 4 chars + ****
    sensitivity_weight: int
    detection_method: str
    confidence: float
    needs_review: bool
    required: bool
    redaction_decision: str
    always_redact: bool
    explanation: str


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
    fields_detected: list[FieldSummary] = field(default_factory=list)
    compliance_notes: ComplianceNotes = field(default_factory=ComplianceNotes)
    redacted_file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def build(cls, scan_id: str, timestamp: str, filename: str, document_type: str,
              doc_confidence: float, context: str, pei_before: float, pei_after: float,
              fields: list, redacted_path: str = "") -> "AuditReport":
        def _mask(val: str) -> str:
            if len(val) <= 4:
                return "****"
            return val[:4] + "****"

        field_summaries = [
            FieldSummary(
                field_name=f.field_name,
                detected_value_masked=_mask(f.field_value),
                sensitivity_weight=f.sensitivity_weight,
                detection_method=f.detection_method,
                confidence=round(f.confidence, 2),
                needs_review=f.needs_review,
                required=f.required,
                redaction_decision=f.redaction_decision,
                always_redact=f.always_redact,
                explanation=f.explanation,
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
            fields_detected=field_summaries,
            redacted_file_path=redacted_path,
        )
