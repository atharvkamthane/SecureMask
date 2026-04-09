from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from securemask.models.detected_field import DetectedField


def redact_image(image_path: str | Path, fields: list[DetectedField], output_path: str | Path) -> Path:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for field in fields:
        if field.redaction_decision == "allow":
            continue
        bbox = field.bounding_box.padded(4, image.width, image.height)
        draw.rectangle(bbox.as_tuple(), fill=(0, 0, 0))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG")
    return output
