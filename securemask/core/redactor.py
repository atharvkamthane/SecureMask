"""Image redaction engine with failure-safe bounds and audit logging.

Modes:
  - redact: white rectangle over bounding box + padding (clean removal)
  - mask: partial black mask that hides the leading part and leaves the tail visible
  - always_redact: forced full white redaction regardless of user decision
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from securemask.config import IDENTIFIER_FIELDS
from securemask.models.detected_field import BoundingBox, DetectedField

logger = logging.getLogger(__name__)

# Fixed redaction colors
_REDACT_FILL = (255, 255, 255)  # white — clean removal
_MASK_FILL = (0, 0, 0)          # black — partial concealment


@dataclass
class RedactionOutcome:
    """Audit record of a redaction decision applied to a specific field."""
    field_name: str
    decision: str
    status: str  # "applied", "clamped", "failed_invalid_geometry", "missing_coordinates", "allowed"
    applied_box: tuple[int, int, int, int] | None
    warning: str | None = None


class Redactor:
    """Apply redaction or masking to document images with failure-safe guards."""

    PADDING = 6
    MIN_MASK_VISIBLE_PX = 18
    MAX_MASK_VISIBLE_PX = 48

    def __init__(self) -> None:
        self.outcomes: list[RedactionOutcome] = []
        self.warnings: list[str] = []

    def _bbox_pixels(self, field: DetectedField, img_w: int, img_h: int) -> BoundingBox:
        """Resolve bbox in image pixels; prefer percentage box when set."""
        if field.bounding_box_pct and img_w > 0 and img_h > 0:
            p = field.bounding_box_pct
            return BoundingBox(
                int(p.x / 100 * img_w),
                int(p.y / 100 * img_h),
                max(1, int(p.width / 100 * img_w)),
                max(1, int(p.height / 100 * img_h)),
            )
        return field.bounding_box

    def redact(
        self,
        image: Image.Image,
        fields: list[DetectedField],
        decisions: dict[str, str],
    ) -> Image.Image:
        """Apply redaction/masking to a copy of the image.

        Guarantees failure-safe operation:
        - Sensitive fields requiring redaction/masking with invalid/missing geometry
          are explicitly flagged as warnings in the audit log.
        - Out-of-bounds coordinates are sanitized and clamped to image dimensions.
        - Outcomes are tracked per field for audit verification.
        """
        img = image.copy()
        draw = ImageDraw.Draw(img)
        img_w, img_h = img.size
        self.outcomes.clear()
        self.warnings.clear()

        for field in fields:
            raw_decision = decisions.get(field.field_name, "allow")
            decision = str(raw_decision).lower().strip() if raw_decision else "allow"

            if field.always_redact:
                decision = "redact"

            if decision == "allow":
                self.outcomes.append(RedactionOutcome(
                    field_name=field.field_name,
                    decision="allow",
                    status="allowed",
                    applied_box=None,
                    warning=None,
                ))
                continue

            # Target requires redaction or masking
            if field.bounding_box is None:
                warn_msg = f"Redaction failure for '{field.field_name}': missing bounding box coordinates."
                logger.warning(warn_msg)
                self.warnings.append(warn_msg)
                field.needs_review = True
                field.metadata["redaction_warning"] = warn_msg
                self.outcomes.append(RedactionOutcome(
                    field_name=field.field_name,
                    decision=decision,
                    status="missing_coordinates",
                    applied_box=None,
                    warning=warn_msg,
                ))
                continue

            bb = self._bbox_pixels(field, img_w, img_h)

            # Check for invalid geometry (tiny placeholder or collapsed coordinates)
            if bb.width <= 2 and bb.height <= 2:
                warn_msg = (
                    f"Redaction failure for '{field.field_name}': placeholder or collapsed "
                    f"geometry ({bb.width}x{bb.height} px). Field remains unredacted; manual review required."
                )
                logger.warning(warn_msg)
                self.warnings.append(warn_msg)
                field.needs_review = True
                field.metadata["redaction_warning"] = warn_msg
                self.outcomes.append(RedactionOutcome(
                    field_name=field.field_name,
                    decision=decision,
                    status="failed_invalid_geometry",
                    applied_box=None,
                    warning=warn_msg,
                ))
                continue

            pad = self.PADDING + (4 if field.field_name in IDENTIFIER_FIELDS else 0)
            raw_x1 = int(bb.x) - pad
            raw_y1 = int(bb.y) - pad
            raw_x2 = int(bb.x) + max(1, int(bb.width)) + pad
            raw_y2 = int(bb.y) + max(1, int(bb.height)) + pad

            # Clamping to valid image bounds
            x1 = max(0, min(img_w - 1, raw_x1))
            y1 = max(0, min(img_h - 1, raw_y1))
            x2 = max(x1 + 1, min(img_w, raw_x2))
            y2 = max(y1 + 1, min(img_h, raw_y2))

            status = "clamped" if (x1 != raw_x1 or y1 != raw_y1 or x2 != raw_x2 or y2 != raw_y2) else "applied"

            applied_box = (x1, y1, x2, y2)

            if decision == "redact":
                draw.rectangle([x1, y1, x2, y2], fill=_REDACT_FILL)
            elif decision == "mask":
                box_width = max(1, x2 - x1)
                visible_ratio = 0.15 if field.field_name in IDENTIFIER_FIELDS else 0.28
                visible_width = min(
                    self.MAX_MASK_VISIBLE_PX,
                    max(self.MIN_MASK_VISIBLE_PX, int(box_width * visible_ratio)),
                    max(1, box_width - 1),  # ensure at least 1 pixel is masked
                )
                mask_x2 = max(x1 + 1, x2 - visible_width)
                draw.rectangle([x1, y1, mask_x2, y2], fill=_MASK_FILL)

            outcome = RedactionOutcome(
                field_name=field.field_name,
                decision=decision,
                status=status,
                applied_box=applied_box,
                warning=None,
            )
            self.outcomes.append(outcome)
            field.metadata["redaction_outcome"] = outcome.status

        return img


def redact_image(
    image_path: str | Path,
    fields: list[DetectedField],
    output_path: str | Path,
    decisions: dict[str, str] | None = None,
) -> Path:
    """Load an image, redact it, and save the protected PNG."""
    if decisions is None:
        decisions = {f.field_name: f.redaction_decision for f in fields}

    image = Image.open(image_path).convert("RGB")
    redactor = Redactor()
    redacted = redactor.redact(image, fields, decisions)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    redacted.save(output, "PNG")
    return output
