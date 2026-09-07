"""Unit tests for Privacy Exposure Index (PEI) redesign.

Validates the formal mathematical properties A through M required by the
SecureMask PEI specification:
A. empty / no detected fields
B. single necessary attribute
C. all excess fields exposed
D. all excess fields redacted
E. necessary PAN fully exposed
F. necessary PAN masked
G. necessary PAN redacted
H. masked PAN PEI < unmasked PAN PEI
I. redacted PAN PEI < masked PAN PEI
J. context switch changes necessity and PEI
K. no result exceeds 100
L. no result falls below 0
M. denominator remains constant before/after redaction
"""
from __future__ import annotations

import pytest

from securemask.core.pei import (
    DEFAULT_RESIDUAL_LAMBDA,
    IDENTIFIER_MASKING_RATIOS,
    PRIMARY_IDENTIFIERS,
    compute_pei,
    compute_pei_after_redaction,
    compute_pei_details,
    get_masking_exposure_factor,
)
from securemask.models.detected_field import BoundingBox, DetectedField


def _make_field(
    name: str,
    weight: int = 2,
    always_redact: bool = False,
) -> DetectedField:
    """Helper to instantiate a DetectedField fixture."""
    return DetectedField(
        field_name=name,
        field_value="DUMMY_VALUE",
        sensitivity_weight=weight,
        detection_method="regex_fuzzy",
        confidence=0.99,
        bounding_box=BoundingBox(0, 0, 100, 20),
        always_redact=always_redact,
    )


class TestPEIProperties:
    # A. empty/no detected fields
    def test_property_a_empty_fields(self):
        details = compute_pei_details([], {})
        assert details.pei == 0.0
        assert details.total_capacity == 0.0
        assert details.raw_excess == 0.0
        assert details.raw_residual == 0.0
        assert compute_pei([], {}) == 0.0
        assert compute_pei_after_redaction([], {}, {}) == 0.0

    # B. single necessary attribute
    def test_property_b_single_necessary_attribute(self):
        name_field = _make_field("name", weight=2)
        nec = {"name": True}
        details = compute_pei_details([name_field], nec)
        assert details.total_capacity == 2.0
        assert details.raw_excess == 0.0
        assert details.raw_residual == 0.0
        assert details.pei == 0.0
        assert compute_pei([name_field], nec) == 0.0

    # C. all excess fields exposed
    def test_property_c_all_excess_fields_exposed(self):
        f1 = _make_field("blood_group", weight=1)
        f2 = _make_field("qr_code", weight=3, always_redact=True)
        f3 = _make_field("father_name", weight=2)
        fields = [f1, f2, f3]
        nec = {"blood_group": False, "qr_code": False, "father_name": False}
        details = compute_pei_details(fields, nec)
        # All are excess and exposed: raw_excess == total_capacity == 6.0
        assert details.total_capacity == 6.0
        assert details.raw_excess == 6.0
        assert details.raw_residual == 0.0
        assert details.pei == 100.0

    # D. all excess fields redacted
    def test_property_d_all_excess_fields_redacted(self):
        f_req = _make_field("name", weight=2)
        f_excess1 = _make_field("photo", weight=2)
        f_excess2 = _make_field("qr_code", weight=3, always_redact=True)
        fields = [f_req, f_excess1, f_excess2]
        nec = {"name": True, "photo": False, "qr_code": False}
        decisions = {"name": "allow", "photo": "redact", "qr_code": "redact"}
        details = compute_pei_details(fields, nec, decisions)
        assert details.raw_excess == 0.0
        assert details.raw_residual == 0.0
        assert details.pei == 0.0
        assert compute_pei_after_redaction(fields, nec, decisions) == 0.0

    # E. necessary PAN fully exposed
    def test_property_e_necessary_pan_fully_exposed(self):
        pan = _make_field("pan_number", weight=5)
        name = _make_field("name", weight=2)
        fields = [pan, name]
        nec = {"pan_number": True, "name": True}
        details = compute_pei_details(fields, nec)
        # raw_excess = 0 (both necessary)
        # raw_residual = lambda * 1.0 * 5 = 2.5
        # total_capacity = 7.0
        # pei = (2.5 / 7.0) * 100 = 35.714... -> 35.7
        assert details.raw_excess == 0.0
        assert details.raw_residual == 2.5
        assert details.total_capacity == 7.0
        assert details.pei > 0.0
        assert details.pei == pytest.approx(35.7, abs=0.1)

    # F. necessary PAN masked
    def test_property_f_necessary_pan_masked(self):
        pan = _make_field("pan_number", weight=5)
        name = _make_field("name", weight=2)
        fields = [pan, name]
        nec = {"pan_number": True, "name": True}
        decisions = {"pan_number": "mask", "name": "allow"}
        details = compute_pei_details(fields, nec, decisions)
        # mu_f for PAN = 4/10 = 0.40
        # raw_residual = lambda * 0.40 * 5 = 0.50 * 2.0 = 1.0
        # total_capacity = 7.0
        # pei = (1.0 / 7.0) * 100 = 14.285... -> 14.3
        assert details.raw_residual == 1.0
        assert details.pei > 0.0
        assert details.pei == pytest.approx(14.3, abs=0.1)

    # G. necessary PAN redacted
    def test_property_g_necessary_pan_redacted(self):
        pan = _make_field("pan_number", weight=5)
        name = _make_field("name", weight=2)
        fields = [pan, name]
        nec = {"pan_number": True, "name": True}
        decisions = {"pan_number": "redact", "name": "allow"}
        details = compute_pei_details(fields, nec, decisions)
        # e_f for PAN = 0.0 -> raw_residual = 0.0
        assert details.raw_excess == 0.0
        assert details.raw_residual == 0.0
        assert details.pei == 0.0
        assert compute_pei_after_redaction(fields, nec, decisions) == 0.0

    # H. masked PAN PEI < unmasked PAN PEI
    def test_property_h_masked_pan_less_than_unmasked(self):
        pan = _make_field("pan_number", weight=5)
        name = _make_field("name", weight=2)
        fields = [pan, name]
        nec = {"pan_number": True, "name": True}

        pei_unmasked = compute_pei(fields, nec)
        pei_masked = compute_pei_after_redaction(
            fields, nec, {"pan_number": "mask", "name": "allow"}
        )
        assert pei_masked < pei_unmasked
        assert pei_unmasked == 35.7
        assert pei_masked == 14.3

    # I. redacted PAN PEI < masked PAN PEI
    def test_property_i_redacted_pan_less_than_masked(self):
        pan = _make_field("pan_number", weight=5)
        name = _make_field("name", weight=2)
        fields = [pan, name]
        nec = {"pan_number": True, "name": True}

        pei_masked = compute_pei_after_redaction(
            fields, nec, {"pan_number": "mask", "name": "allow"}
        )
        pei_redacted = compute_pei_after_redaction(
            fields, nec, {"pan_number": "redact", "name": "allow"}
        )
        assert pei_redacted < pei_masked
        assert pei_redacted == 0.0

    # J. context switch changes necessity and PEI
    def test_property_j_context_switch_changes_necessity_and_pei(self):
        pan = _make_field("pan_number", weight=5)
        name = _make_field("name", weight=2)
        fields = [pan, name]

        # In identity_verification: PAN is necessary (attenuated residual: lambda * 5 = 2.5)
        nec_identity = {"pan_number": True, "name": True}
        pei_identity = compute_pei(fields, nec_identity)

        # In general_upload: PAN is excess (full penalty: 1.0 * 5 = 5.0)
        nec_general = {"pan_number": False, "name": True}
        pei_general = compute_pei(fields, nec_general)

        assert pei_general > pei_identity
        assert pei_identity == 35.7
        # In general upload: raw_excess = 5.0, total = 7.0 -> 5.0/7.0*100 = 71.4
        assert pei_general == pytest.approx(71.4, abs=0.1)

    # K. no result exceeds 100
    @pytest.mark.parametrize("lam", [0.0, 0.25, 0.50, 0.75, 1.00])
    def test_property_k_no_result_exceeds_100(self, lam):
        fields = [
            _make_field("pan_number", weight=5),
            _make_field("aadhaar_number", weight=5),
            _make_field("dob", weight=3),
            _make_field("photo", weight=2, always_redact=True),
        ]
        # Test completely exposed
        for nec in [
            {"pan_number": True, "aadhaar_number": True, "dob": True, "photo": False},
            {"pan_number": False, "aadhaar_number": False, "dob": False, "photo": False},
        ]:
            pei = compute_pei(fields, nec, lambda_param=lam)
            assert 0.0 <= pei <= 100.0

    # L. no result falls below 0
    def test_property_l_no_result_falls_below_zero(self):
        fields = [_make_field("name", weight=2)]
        nec = {"name": True}
        pei = compute_pei(fields, nec)
        assert pei >= 0.0

        pei_redacted = compute_pei_after_redaction(fields, nec, {"name": "redact"})
        assert pei_redacted >= 0.0

    # M. denominator remains constant before/after redaction
    def test_property_m_denominator_constant_before_after_redaction(self):
        fields = [
            _make_field("name", weight=2),
            _make_field("dob", weight=3),
            _make_field("pan_number", weight=5),
            _make_field("photo", weight=2),
        ]
        nec = {"name": True, "dob": True, "pan_number": True, "photo": False}
        decisions = {"name": "allow", "dob": "allow", "pan_number": "mask", "photo": "redact"}

        details_before = compute_pei_details(fields, nec)
        details_after = compute_pei_details(fields, nec, decisions)

        assert details_before.total_capacity == details_after.total_capacity
        assert details_before.total_capacity == 12.0
        # Verify strict monotonic decrease
        assert details_after.pei < details_before.pei


class TestPEIExplainabilityAndRatios:
    def test_schema_masking_ratios(self):
        assert get_masking_exposure_factor("aadhaar_number") == pytest.approx(4.0 / 12.0)
        assert get_masking_exposure_factor("pan_number") == pytest.approx(4.0 / 10.0)
        assert get_masking_exposure_factor("passport_number") == pytest.approx(4.0 / 8.0)
        assert get_masking_exposure_factor("epic_number") == pytest.approx(4.0 / 10.0)
        assert get_masking_exposure_factor("dl_number") == pytest.approx(4.0 / 15.0)
        # Default fallback
        assert get_masking_exposure_factor("unknown_id") == 0.40

    def test_explainability_components(self):
        fields = [
            _make_field("aadhaar_number", weight=5),
            _make_field("name", weight=2),
            _make_field("photo", weight=2),
        ]
        nec = {"aadhaar_number": True, "name": True, "photo": False}
        decisions = {"aadhaar_number": "mask", "name": "allow", "photo": "allow"}

        details = compute_pei_details(fields, nec, decisions, lambda_param=0.50)
        # total_capacity = 5 + 2 + 2 = 9.0
        # photo is excess, allowed -> raw_excess = 1.0 * 2 = 2.0
        # aadhaar is necessary primary id, masked -> e_f = 4/12 = 1/3
        # raw_residual = lambda * (1/3) * 5 = 0.5 * (5/3) = 0.8333...
        # pei_excess = (2.0 / 9.0) * 100 = 22.22%
        # pei_residual = (0.8333 / 9.0) * 100 = 9.26%
        # raw_pei = 31.48% -> rounded pei = 31.5%
        assert details.total_capacity == 9.0
        assert details.raw_excess == pytest.approx(2.0, abs=1e-4)
        assert details.raw_residual == pytest.approx(5.0 / 6.0, abs=1e-4)
        assert details.pei_excess == pytest.approx(22.22, abs=0.1)
        assert details.pei_residual == pytest.approx(9.26, abs=0.1)
        assert details.pei == 31.5
        assert details.lambda_param == 0.50
