"""Image redaction engine.

Modes:
  - redact: filled black rectangle over bounding box + 4px padding
  - mask: partial mask — show first 40px, black bar over rest
  - always_redact: forced full redaction regardless of user decision
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from PIL import Image, ImageDraw

from securemask.models.detected_field import DetectedField


class Redactor:
    """Apply redaction or masking to document images."""

    PADDING = 4

    def redact(self, image: Image.Image, fields: list[DetectedField],
               decisions: dict[str, str]) -> Image.Image:
        """Apply redaction/masking to a copy of the image.

        Args:
            image: Original PIL Image
            fields: List of detected fields with bounding boxes
            decisions: {field_name: "redact" | "mask" | "allow"}

        Returns:
            New PIL Image with redactions applied.
        """
        img = image.copy()
        draw = ImageDraw.Draw(img)

        for field in fields:
            decision = decisions.get(field.field_name, "allow")

            if field.always_redact:
                decision = "redact"  # force override

            if decision == "allow":
                continue

            if field.bounding_box is None:
                continue

            # Skip placeholder bounding boxes — these mean the OCR couldn't
            # locate the field spatially. Redacting at (0,0) would black out
            # the document header area incorrectly.
            bb = field.bounding_box
            if bb.width <= 2 and bb.height <= 2:
                logger.debug("Skipping redaction for %s: placeholder bbox", field.field_name)
                continue

            x = int(bb.x) - self.PADDING
            y = int(bb.y) - self.PADDING
            x2 = x + int(bb.width) + self.PADDING * 2
            y2 = y + int(bb.height) + self.PADDING * 2

            # Clamp to image bounds
            x = max(0, x)
            y = max(0, y)
            x2 = min(img.width, x2)
            y2 = min(img.height, y2)

            if decision == "redact":
                draw.rectangle([x, y, x2, y2], fill=(255, 255, 255))
            elif decision == "mask":
                # Partial mask — show first 40px, white bar over rest
                visible_width = min(40, x2 - x)
                draw.rectangle([x + visible_width, y, x2, y2], fill=(255, 255, 255))

        return img


def redact_image(image_path: str | Path, fields: list[DetectedField],
                 output_path: str | Path, decisions: dict[str, str] | None = None) -> Path:
    """Convenience function: load image, redact, save."""
    if decisions is None:
        decisions = {f.field_name: f.redaction_decision for f in fields}

    image = Image.open(image_path).convert("RGB")
    redactor = Redactor()
    redacted = redactor.redact(image, fields, decisions)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    redacted.save(output, "PNG")
    return output
