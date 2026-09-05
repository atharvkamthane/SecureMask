"""Pure metric-calculation functions — no I/O, no pipeline dependencies.

All functions operate on primitive Python types so they can be tested
with small synthetic fixtures without needing real images or models.
"""
from __future__ import annotations

from typing import Sequence


# ------------------------------------------------------------------
# Precision / Recall / F1
# ------------------------------------------------------------------

def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Compute precision, recall, and F1 from raw counts.

    Returns (precision, recall, f1), each in [0.0, 1.0].
    Division-by-zero cases return 0.0.
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return (round(precision, 6), round(recall, 6), round(f1, 6))


def aggregate_classification_metrics(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str],
) -> dict[str, dict[str, float]]:
    """Per-class precision / recall / F1 from paired label lists.

    Returns ``{label: {"precision": ..., "recall": ..., "f1": ...}}``.
    """
    result: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        p, r, f = precision_recall_f1(tp, fp, fn)
        result[label] = {"precision": p, "recall": r, "f1": f}
    return result


# ------------------------------------------------------------------
# Confusion matrix
# ------------------------------------------------------------------

def confusion_matrix(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    labels: Sequence[str],
) -> dict[str, dict[str, int]]:
    """Build a confusion matrix as a nested dict.

    ``matrix[true_label][pred_label] = count``
    """
    matrix: dict[str, dict[str, int]] = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return matrix


# ------------------------------------------------------------------
# IoU (Intersection over Union) for bounding boxes
# ------------------------------------------------------------------

def compute_iou(box_a: Sequence[int | float], box_b: Sequence[int | float]) -> float:
    """Compute IoU between two boxes, each as ``[x, y, w, h]``.

    Returns a float in [0.0, 1.0].
    """
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    # Convert to (x1, y1, x2, y2)
    ax1, ay1, ax2, ay2 = ax, ay, ax + aw, ay + ah
    bx1, by1, bx2, by2 = bx, by, bx + bw, by + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = aw * ah
    area_b = bw * bh
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0
    return round(inter_area / union, 6)


# ------------------------------------------------------------------
# Exact-match comparison
# ------------------------------------------------------------------

def exact_match(predicted: str, ground_truth: str, *, normalize: bool = True) -> bool:
    """Check whether two strings match.

    When *normalize* is ``True``, comparison strips whitespace and is
    case-insensitive. Otherwise a strict byte-for-byte match is used.
    """
    if normalize:
        return _normalize_value(predicted) == _normalize_value(ground_truth)
    return predicted == ground_truth


def _normalize_value(v: str) -> str:
    """Strip whitespace (including inner spaces) and lowercase."""
    return "".join(v.split()).lower()
