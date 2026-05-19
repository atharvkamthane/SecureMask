"""Image redaction engine.

Modes:
  - redact: adaptive paper-colored rectangle over bounding box + padding
  - mask: partial mask that hides the leading part and leaves the tail visible
  - always_redact: forced full redaction regardless of user decision
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from securemask.models.detected_field import DetectedField

logger = logging.getLogger(__name__)


class Redactor:
    """Apply redaction or masking to document images."""

    PADDING = 4
    MIN_MASK_VISIBLE_PX = 28
    MAX_MASK_VISIBLE_PX = 90

    def _background_fill(self, img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
        """Estimate local document background so the redaction blends with the page."""
        x, y, x2, y2 = box
        sample_pad = max(self.PADDING * 3, 12)
        sx = max(0, x - sample_pad)
        sy = max(0, y - sample_pad)
        sx2 = min(img.width, x2 + sample_pad)
        sy2 = min(img.height, y2 + sample_pad)

        region = np.asarray(img.crop((sx, sy, sx2, sy2)).convert("RGB"))
        if region.size == 0:
            return (255, 255, 255)

        mask = np.ones(region.shape[:2], dtype=bool)
        inner_x1 = max(0, x - sx)
        inner_y1 = max(0, y - sy)
        inner_x2 = min(region.shape[1], x2 - sx)
        inner_y2 = min(region.shape[0], y2 - sy)
        mask[inner_y1:inner_y2, inner_x1:inner_x2] = False

        samples = region[mask]
        if samples.size == 0:
            samples = region.reshape(-1, 3)

        luminance = samples.mean(axis=1)
        light_samples = samples[luminance >= 170]
        chosen = light_samples if len(light_samples) >= 12 else samples
        median = np.median(chosen, axis=0)
        return tuple(int(v) for v in median)

    def redact(
        self,
        image: Image.Image,
        fields: list[DetectedField],
        decisions: dict[str, str],
    ) -> Image.Image:
        """Apply redaction/masking to a copy of the image."""
        img = image.copy()
        draw = ImageDraw.Draw(img)

        for field in fields:
            decision = decisions.get(field.field_name, "allow")

            if field.always_redact:
                decision = "redact"

            if decision == "allow" or field.bounding_box is None:
                continue

            bb = field.bounding_box
            if bb.width <= 2 and bb.height <= 2:
                logger.debug("Skipping redaction for %s: placeholder bbox", field.field_name)
                continue

            x = max(0, int(bb.x) - self.PADDING)
            y = max(0, int(bb.y) - self.PADDING)
            x2 = min(img.width, int(bb.x) + int(bb.width) + self.PADDING)
            y2 = min(img.height, int(bb.y) + int(bb.height) + self.PADDING)
            if x2 <= x or y2 <= y:
                continue

            fill = self._background_fill(img, (x, y, x2, y2))

            if decision == "redact":
                draw.rectangle([x, y, x2, y2], fill=fill)
            elif decision == "mask":
                box_width = max(1, x2 - x)
                visible_width = min(
                    self.MAX_MASK_VISIBLE_PX,
                    max(self.MIN_MASK_VISIBLE_PX, int(box_width * 0.28)),
                    box_width,
                )
                draw.rectangle([x, y, max(x, x2 - visible_width), y2], fill=fill)

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
