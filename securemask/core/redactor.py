"""Image redaction engine.

Modes:
  - redact: white rectangle over bounding box + padding (clean removal)
  - mask: partial black mask that hides the leading part and leaves the tail visible
  - always_redact: forced full white redaction regardless of user decision
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from securemask.models.detected_field import BoundingBox, DetectedField

logger = logging.getLogger(__name__)
from securemask.config import IDENTIFIER_FIELDS

# Fixed redaction colors
_REDACT_FILL = (255, 255, 255)  # white — clean removal
_MASK_FILL = (0, 0, 0)          # black — partial concealment


class Redactor:
    """Apply redaction or masking to document images."""

    PADDING = 6
    MIN_MASK_VISIBLE_PX = 18
    MAX_MASK_VISIBLE_PX = 48

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
        """Apply redaction/masking to a copy of the image."""
        img = image.copy()
        draw = ImageDraw.Draw(img)
        img_w, img_h = img.size

        for field in fields:
            decision = decisions.get(field.field_name, "allow")

            if field.always_redact:
                decision = "redact"

            if decision == "allow" or field.bounding_box is None:
                continue

            bb = self._bbox_pixels(field, img_w, img_h)
            if bb.width <= 2 and bb.height <= 2:
                logger.debug("Skipping redaction for %s: placeholder bbox", field.field_name)
                continue

            pad = self.PADDING + (4 if field.field_name in IDENTIFIER_FIELDS else 0)
            x = max(0, int(bb.x) - pad)
            y = max(0, int(bb.y) - pad)
            x2 = min(img.width, int(bb.x) + int(bb.width) + pad)
            y2 = min(img.height, int(bb.y) + int(bb.height) + pad)
            if x2 <= x or y2 <= y:
                continue

            if decision == "redact":
                draw.rectangle([x, y, x2, y2], fill=_REDACT_FILL)
            elif decision == "mask":
                box_width = max(1, x2 - x)
                visible_ratio = 0.15 if field.field_name in IDENTIFIER_FIELDS else 0.28
                visible_width = min(
                    self.MAX_MASK_VISIBLE_PX,
                    max(self.MIN_MASK_VISIBLE_PX, int(box_width * visible_ratio)),
                    box_width,
                )
                draw.rectangle([x, y, max(x, x2 - visible_width), y2], fill=_MASK_FILL)

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
