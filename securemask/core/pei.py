"""Privacy Exposure Index (PEI) scoring.

PEI measures residual privacy exposure caused by information disclosed beyond
what is strictly necessary for the declared transaction context.

FORMULATION:
    PEI(D, c) = [
        Sum_{excess} (e_f * w_f) + lambda * Sum_{id, req} (e_f * w_f)
    ] / [
        Sum_{all} w_f
    ] * 100

Definitions:
1. Excess fields (F_excess):
   n_f == False OR always_redact == True
2. Necessary primary identifiers (F_id,req):
   n_f == True AND not always_redact AND field_name in PRIMARY_IDENTIFIERS
   (aadhaar_number, pan_number, passport_number, dl_number, epic_number)
3. Necessary atomic attributes:
   Name, DOB, Address, etc. Contribute zero PEI when contextually necessary.
4. Decision exposure e_f:
   - allow  -> e_f = 1.0
   - redact -> e_f = 0.0
   - mask   -> e_f = mu_f (schema-specific visible character ratio)
5. Masking exposure factor mu_f:
   mu_f = visible_identifier_characters / total_identifier_characters
6. Residual identifier attenuation lambda:
   lambda = 0.50 (Policy calibration parameter reflecting institutional risk tolerance;
   NOT an experimentally proven universal physical constant or theoretically derived value).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from securemask.models.detected_field import DetectedField

# Recognized primary identifier field names across supported Indian ID documents
PRIMARY_IDENTIFIERS: frozenset[str] = frozenset({
    "aadhaar_number",
    "pan_number",
    "passport_number",
    "dl_number",
    "epic_number",
})

# Schema-derived visible character ratios: visible_characters / total_characters
IDENTIFIER_MASKING_RATIOS: dict[str, float] = {
    "aadhaar_number": 4.0 / 12.0,   # 4 visible / 12 total digits (~0.3333)
    "pan_number": 4.0 / 10.0,       # 4 visible / 10 total alphanumeric characters (0.40)
    "passport_number": 4.0 / 8.0,   # 4 visible / 8 total alphanumeric characters (0.50)
    "epic_number": 4.0 / 10.0,      # 4 visible / 10 total alphanumeric characters (0.40)
    "dl_number": 4.0 / 15.0,        # 4 visible / 15 total alphanumeric characters (~0.2667)
}

# Fallback masking ratio for identifiers with unlisted schema
DEFAULT_MASKING_RATIO: float = 0.40

# Policy calibration parameter attenuating the risk of necessary primary identifiers.
# NOTE: lambda = 0.50 is an institutional policy parameter, NOT a universal constant.
DEFAULT_RESIDUAL_LAMBDA: float = 0.50


def get_masking_exposure_factor(field_name: str) -> float:
    """Return schema-specific masking exposure factor mu_f for an identifier.

    mu_f = visible_identifier_characters / total_identifier_characters
    """
    return IDENTIFIER_MASKING_RATIOS.get(field_name, DEFAULT_MASKING_RATIO)


@dataclass(frozen=True)
class PEIDetails:
    """Detailed breakdown of Privacy Exposure Index components for audit & explainability."""

    pei: float
    raw_excess: float
    raw_residual: float
    total_capacity: float
    pei_excess: float
    pei_residual: float
    lambda_param: float


def compute_pei_details(
    detected_fields: list[DetectedField],
    necessity_results: dict[str, bool],
    redaction_decisions: dict[str, str] | None = None,
    lambda_param: float = DEFAULT_RESIDUAL_LAMBDA,
) -> PEIDetails:
    """Compute detailed breakdown of the Privacy Exposure Index (PEI).

    Formula:
        PEI(D, c) = [
            Sum_{excess} (e_f * w_f) + lambda * Sum_{id, req} (e_f * w_f)
        ] / [
            Sum_{all} w_f
        ] * 100

    Args:
        detected_fields: List of all DetectedField instances on the document.
        necessity_results: Mapping from field_name to necessity bool (True if necessary).
        redaction_decisions: Optional mapping from field_name to decision
            ("allow", "mask", "redact"). If None, all fields default to "allow" (1.0).
        lambda_param: Policy calibration parameter attenuating necessary primary identifiers.

    Returns:
        PEIDetails with components and final PEI score.
    """
    # Clamp lambda parameter to non-negative range
    lambda_param = max(0.0, float(lambda_param))

    # Defensive deduplication by field_name: retain highest-weight/confidence entry
    seen_fields: dict[str, DetectedField] = {}
    for f in detected_fields:
        if not hasattr(f, "field_name") or not f.field_name:
            continue
        fname = str(f.field_name)
        if fname not in seen_fields:
            seen_fields[fname] = f
        else:
            # If duplicate exists, preserve the one with higher weight/confidence
            curr = seen_fields[fname]
            if (f.sensitivity_weight, getattr(f, "confidence", 0.0)) > (curr.sensitivity_weight, getattr(curr, "confidence", 0.0)):
                seen_fields[fname] = f

    sanitized_fields = list(seen_fields.values())
    if not sanitized_fields:
        return PEIDetails(
            pei=0.0,
            raw_excess=0.0,
            raw_residual=0.0,
            total_capacity=0.0,
            pei_excess=0.0,
            pei_residual=0.0,
            lambda_param=lambda_param,
        )

    total_capacity = sum(max(0.0, float(field.sensitivity_weight)) for field in sanitized_fields)
    if total_capacity <= 0.0:
        return PEIDetails(
            pei=0.0,
            raw_excess=0.0,
            raw_residual=0.0,
            total_capacity=0.0,
            pei_excess=0.0,
            pei_residual=0.0,
            lambda_param=lambda_param,
        )

    raw_excess = 0.0
    raw_residual = 0.0

    for field in sanitized_fields:
        w_f = max(0.0, float(field.sensitivity_weight))

        # Determine decision exposure factor e_f
        if redaction_decisions is None:
            decision = "allow"
        else:
            raw_decision = redaction_decisions.get(field.field_name, "allow")
            decision = str(raw_decision).lower().strip() if raw_decision else "allow"

        if decision == "redact":
            e_f = 0.0
        elif decision == "mask":
            e_f = get_masking_exposure_factor(field.field_name)
        else:
            # "allow" or unrecognized decision defaults conservatively to full exposure (1.0)
            e_f = 1.0

        is_necessary = bool(necessity_results.get(field.field_name, False))
        is_excess = bool(getattr(field, "always_redact", False)) or (not is_necessary)

        if is_excess:
            raw_excess += e_f * w_f
        elif field.field_name in PRIMARY_IDENTIFIERS:
            # Necessary primary identifier: attenuated by policy lambda
            raw_residual += lambda_param * (e_f * w_f)
        else:
            # Necessary atomic attribute (name, dob, address, etc.):
            # Contributes zero PEI when contextually necessary
            pass

    pei_excess = (raw_excess / total_capacity) * 100.0
    pei_residual = (raw_residual / total_capacity) * 100.0
    raw_pei = pei_excess + pei_residual
    final_pei = round(min(max(raw_pei, 0.0), 100.0), 1)

    return PEIDetails(
        pei=final_pei,
        raw_excess=round(raw_excess, 4),
        raw_residual=round(raw_residual, 4),
        total_capacity=round(total_capacity, 4),
        pei_excess=round(pei_excess, 2),
        pei_residual=round(pei_residual, 2),
        lambda_param=lambda_param,
    )


def compute_pei(
    detected_fields: list[DetectedField],
    necessity_results: dict[str, bool],
    redaction_decisions: dict[str, str] | None = None,
    lambda_param: float = DEFAULT_RESIDUAL_LAMBDA,
) -> float:
    """Compute Privacy Exposure Index (PEI).

    Returns the final PEI score rounded to 1 decimal place, bounded in [0.0, 100.0].
    """
    details = compute_pei_details(
        detected_fields=detected_fields,
        necessity_results=necessity_results,
        redaction_decisions=redaction_decisions,
        lambda_param=lambda_param,
    )
    return details.pei


def compute_pei_after_redaction(
    detected_fields: list[DetectedField],
    necessity_results: dict[str, bool],
    redaction_decisions: dict[str, str],
    lambda_param: float = DEFAULT_RESIDUAL_LAMBDA,
) -> float:
    """Compute PEI after redaction decisions have been applied.

    CRITICAL BUG FIX: Does NOT filter detected_fields before computing PEI.
    The complete original detected field set is always retained as the
    normalization denominator (total_capacity), ensuring:
    1. Consistent baseline before and after redaction.
    2. No artificial mathematical floor for necessary fields.
    3. Monotonic decrease: PEI_redacted <= PEI_original.
    """
    return compute_pei(
        detected_fields=detected_fields,
        necessity_results=necessity_results,
        redaction_decisions=redaction_decisions,
        lambda_param=lambda_param,
    )
