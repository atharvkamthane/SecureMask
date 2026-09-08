"""Unit tests for failure-safe redaction engine (Redactor)."""
from __future__ import annotations

import pytest
from PIL import Image

from securemask.core.redactor import Redactor, RedactionOutcome
from securemask.models.detected_field import BoundingBox, DetectedField


def _make_field(
    name: str,
    bbox: BoundingBox | None,
    always_redact: bool = False,
) -> DetectedField:
    return DetectedField(
        field_name=name,
        field_value="SAMPLE_SECRET",
        sensitivity_weight=5,
        detection_method="regex_fuzzy",
        confidence=0.95,
        bounding_box=bbox,
        always_redact=always_redact,
    )


class TestRedactorFailureSafety:
    def test_clean_redaction_and_masking(self):
        img = Image.new("RGB", (200, 200), color=(100, 100, 100))
        f_redact = _make_field("aadhaar_number", BoundingBox(20, 20, 80, 20), always_redact=True)
        f_mask = _make_field("pan_number", BoundingBox(20, 80, 100, 25))

        redactor = Redactor()
        redacted = redactor.redact(
            img,
            [f_redact, f_mask],
            {"aadhaar_number": "redact", "pan_number": "mask"},
        )

        assert len(redactor.outcomes) == 2
        assert redactor.outcomes[0].status == "applied"
        assert redactor.outcomes[1].status == "applied"
        assert len(redactor.warnings) == 0

        # Pixel check: redacted area should be white (255, 255, 255)
        pixel_redacted = redacted.getpixel((30, 30))
        assert pixel_redacted == (255, 255, 255)

        # Masked area should have black (0, 0, 0)
        pixel_masked = redacted.getpixel((25, 85))
        assert pixel_masked == (0, 0, 0)

    def test_missing_coordinates_generates_warning(self):
        img = Image.new("RGB", (200, 200), color=(128, 128, 128))
        f_missing = _make_field("pan_number", None)

        redactor = Redactor()
        redacted = redactor.redact(img, [f_missing], {"pan_number": "redact"})

        assert len(redactor.warnings) == 1
        assert "missing bounding box" in redactor.warnings[0]
        assert redactor.outcomes[0].status == "missing_coordinates"
        assert f_missing.needs_review is True
        assert "redaction_warning" in f_missing.metadata

    def test_tiny_collapsed_geometry_generates_warning(self):
        img = Image.new("RGB", (200, 200), color=(128, 128, 128))
        # 1x1 placeholder bbox
        f_tiny = _make_field("passport_number", BoundingBox(50, 50, 1, 1))

        redactor = Redactor()
        redacted = redactor.redact(img, [f_tiny], {"passport_number": "redact"})

        assert len(redactor.warnings) == 1
        assert "collapsed geometry" in redactor.warnings[0]
        assert redactor.outcomes[0].status == "failed_invalid_geometry"
        assert f_tiny.needs_review is True

    def test_out_of_bounds_clamped_safely(self):
        img = Image.new("RGB", (100, 100), color=(200, 200, 200))
        # Bounding box exceeding image dimensions: starts at 80, width 50 -> reaches 130
        f_oob = _make_field("signature", BoundingBox(80, 80, 50, 50))

        redactor = Redactor()
        redacted = redactor.redact(img, [f_oob], {"signature": "redact"})

        assert redactor.outcomes[0].status == "clamped"
        # Coordinates must be clamped within image (<= 100)
        x1, y1, x2, y2 = redactor.outcomes[0].applied_box
        assert x1 >= 0 and y1 >= 0
        assert x2 <= 100 and y2 <= 100
        assert x2 > x1 and y2 > y1
