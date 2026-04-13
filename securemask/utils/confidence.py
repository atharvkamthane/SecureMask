"""Confidence aggregation helpers."""
from __future__ import annotations


def weighted_confidence(confidences: list[float], weights: list[float] | None = None) -> float:
    """Compute weighted average confidence."""
    if not confidences:
        return 0.0
    if weights is None:
        return sum(confidences) / len(confidences)
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    return sum(c * w for c, w in zip(confidences, weights)) / total_weight


def confidence_label(confidence: float) -> str:
    """Return a human-readable confidence label."""
    if confidence >= 0.90:
        return "high"
    if confidence >= 0.70:
        return "medium"
    return "low"
