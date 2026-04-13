"""Privacy Exposure Index (PEI) scoring.

PEI measures how much personal data is exposed. Higher = more risk.
Formula considers: sensitivity weight, necessity status, always_redact flags.
"""
from __future__ import annotations

from securemask.models.detected_field import DetectedField


def compute_pei(detected_fields: list[DetectedField],
                necessity_results: dict[str, bool]) -> float:
    """Compute PEI score before redaction.

    PEI = (raw_score / max_possible) * 100
    - always_redact fields: full penalty (w × 10)
    - excess (not required): full penalty (w × 10)
    - required: minor exposure (w × 2)
    """
    raw_score = 0
    max_possible = 0

    for field in detected_fields:
        w = field.sensitivity_weight
        max_possible += w * 10

        if field.always_redact:
            raw_score += w * 10
        elif not necessity_results.get(field.field_name, False):
            raw_score += w * 10
        else:
            raw_score += w * 2

    if max_possible == 0:
        return 0.0

    pei = (raw_score / max_possible) * 100
    return round(min(pei, 100.0), 1)


def compute_pei_after_redaction(detected_fields: list[DetectedField],
                                 necessity_results: dict[str, bool],
                                 redaction_decisions: dict[str, str]) -> float:
    """Compute PEI after redaction — only count fields where decision == 'allow'.

    Fields that are redacted/masked are no longer exposed.
    """
    allowed_fields = [
        f for f in detected_fields
        if redaction_decisions.get(f.field_name) == "allow"
        and not f.always_redact
    ]
    return compute_pei(allowed_fields, necessity_results)
