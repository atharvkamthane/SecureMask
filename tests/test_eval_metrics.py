"""Tests for securemask.eval.metrics — pure arithmetic, synthetic fixtures only.

These tests validate the metric-calculation functions using small known
inputs, not real pipeline output. This is the one place where synthetic
data is appropriate because we're testing math, not producing paper results.
"""
from __future__ import annotations

import pytest

from securemask.eval.metrics import (
    aggregate_classification_metrics,
    compute_iou,
    confusion_matrix,
    exact_match,
    precision_recall_f1,
)


# ==================================================================
# precision_recall_f1
# ==================================================================

class TestPrecisionRecallF1:
    def test_basic(self):
        # 8 TP, 2 FP, 1 FN → precision=0.8, recall=0.888..., F1=0.842...
        p, r, f = precision_recall_f1(8, 2, 1)
        assert p == pytest.approx(0.8, abs=1e-4)
        assert r == pytest.approx(8 / 9, abs=1e-4)
        assert f == pytest.approx(2 * 0.8 * (8 / 9) / (0.8 + 8 / 9), abs=1e-4)

    def test_perfect(self):
        p, r, f = precision_recall_f1(10, 0, 0)
        assert p == 1.0
        assert r == 1.0
        assert f == 1.0

    def test_all_zeros(self):
        p, r, f = precision_recall_f1(0, 0, 0)
        assert p == 0.0
        assert r == 0.0
        assert f == 0.0

    def test_no_true_positives(self):
        p, r, f = precision_recall_f1(0, 5, 3)
        assert p == 0.0
        assert r == 0.0
        assert f == 0.0

    def test_no_false_positives(self):
        p, r, f = precision_recall_f1(5, 0, 2)
        assert p == 1.0
        assert r == pytest.approx(5 / 7, abs=1e-4)

    def test_no_false_negatives(self):
        p, r, f = precision_recall_f1(5, 3, 0)
        assert r == 1.0
        assert p == pytest.approx(5 / 8, abs=1e-4)


# ==================================================================
# compute_iou
# ==================================================================

class TestComputeIoU:
    def test_perfect_overlap(self):
        box = [10, 20, 100, 50]
        assert compute_iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        a = [0, 0, 10, 10]
        b = [20, 20, 10, 10]
        assert compute_iou(a, b) == 0.0

    def test_partial_overlap(self):
        a = [0, 0, 10, 10]   # area = 100
        b = [5, 5, 10, 10]   # area = 100
        # Intersection: (5,5)→(10,10) = 5×5 = 25
        # Union: 100 + 100 - 25 = 175
        assert compute_iou(a, b) == pytest.approx(25 / 175, abs=1e-4)

    def test_edge_touching(self):
        # Boxes share an edge but have zero intersection area
        a = [0, 0, 10, 10]
        b = [10, 0, 10, 10]
        assert compute_iou(a, b) == 0.0

    def test_contained(self):
        outer = [0, 0, 100, 100]
        inner = [25, 25, 50, 50]
        # Intersection = inner area = 2500
        # Union = 10000 + 2500 - 2500 = 10000
        assert compute_iou(outer, inner) == pytest.approx(2500 / 10000, abs=1e-4)

    def test_zero_area_box(self):
        a = [0, 0, 0, 0]
        b = [0, 0, 10, 10]
        assert compute_iou(a, b) == 0.0


# ==================================================================
# exact_match
# ==================================================================

class TestExactMatch:
    def test_identical(self):
        assert exact_match("hello", "hello") is True

    def test_normalized_whitespace(self):
        assert exact_match("2530 0479 3566", "253004793566", normalize=True) is True

    def test_normalized_case(self):
        assert exact_match("Atharv", "atharv", normalize=True) is True

    def test_strict_whitespace(self):
        assert exact_match("2530 0479 3566", "253004793566", normalize=False) is False

    def test_strict_case(self):
        assert exact_match("Atharv", "atharv", normalize=False) is False

    def test_empty_strings(self):
        assert exact_match("", "") is True

    def test_different_values(self):
        assert exact_match("abc", "xyz") is False


# ==================================================================
# confusion_matrix
# ==================================================================

class TestConfusionMatrix:
    def test_structure(self):
        labels = ["a", "b", "c"]
        y_true = ["a", "a", "b", "c"]
        y_pred = ["a", "b", "b", "c"]
        cm = confusion_matrix(y_true, y_pred, labels)

        assert set(cm.keys()) == set(labels)
        for label in labels:
            assert set(cm[label].keys()) == set(labels)

        # Check specific cells
        assert cm["a"]["a"] == 1  # correct
        assert cm["a"]["b"] == 1  # misclassified a as b
        assert cm["b"]["b"] == 1
        assert cm["c"]["c"] == 1

    def test_all_correct(self):
        labels = ["x", "y"]
        y_true = ["x", "x", "y", "y"]
        y_pred = ["x", "x", "y", "y"]
        cm = confusion_matrix(y_true, y_pred, labels)
        assert cm["x"]["x"] == 2
        assert cm["y"]["y"] == 2
        assert cm["x"]["y"] == 0
        assert cm["y"]["x"] == 0


# ==================================================================
# aggregate_classification_metrics
# ==================================================================

class TestAggregateClassificationMetrics:
    def test_basic(self):
        labels = ["cat", "dog"]
        y_true = ["cat", "cat", "dog", "dog", "dog"]
        y_pred = ["cat", "dog", "dog", "dog", "cat"]

        result = aggregate_classification_metrics(y_true, y_pred, labels)

        assert "cat" in result
        assert "dog" in result

        # cat: TP=1, FP=1 (predicted cat but was dog), FN=1 (was cat but predicted dog)
        assert result["cat"]["precision"] == pytest.approx(1 / 2, abs=1e-4)
        assert result["cat"]["recall"] == pytest.approx(1 / 2, abs=1e-4)

        # dog: TP=2, FP=1 (predicted dog but was cat), FN=1 (was dog but predicted cat)
        assert result["dog"]["precision"] == pytest.approx(2 / 3, abs=1e-4)
        assert result["dog"]["recall"] == pytest.approx(2 / 3, abs=1e-4)

    def test_empty_class(self):
        labels = ["a", "b", "c"]
        y_true = ["a", "a"]
        y_pred = ["a", "a"]

        result = aggregate_classification_metrics(y_true, y_pred, labels)
        assert result["c"]["precision"] == 0.0
        assert result["c"]["recall"] == 0.0
        assert result["c"]["f1"] == 0.0
