from __future__ import annotations

from securemask.models.detected_field import DetectedField


def compute_pei(fields: list[DetectedField], after_redaction: bool = False) -> float:
    considered = [field for field in fields if not after_redaction or field.redaction_decision == "allow"]
    if not considered:
        return 0.0
    raw_score = 0
    max_possible = 0
    for field in considered:
        weight = field.sensitivity_weight
        max_possible += weight * 10
        raw_score += weight * (2 if field.required else 10)
    if max_possible == 0:
        return 0.0
    return min(round((raw_score / max_possible) * 100, 1), 100.0)
