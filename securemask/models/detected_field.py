from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    def padded(self, padding: int, max_width: int, max_height: int) -> "BoundingBox":
        x = max(0, self.x - padding)
        y = max(0, self.y - padding)
        right = min(max_width, self.x + self.width + padding)
        bottom = min(max_height, self.y + self.height + padding)
        return BoundingBox(x=x, y=y, width=max(0, right - x), height=max(0, bottom - y))

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


@dataclass
class DetectedField:
    field_name: str
    field_value: str
    sensitivity_weight: int
    detection_method: str
    confidence: float
    bounding_box: BoundingBox
    explanation: str = ""
    required: bool = False
    redaction_decision: str = "redact"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("metadata", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DetectedField":
        bbox = data.get("bounding_box") or {}
        return cls(
            field_name=data["field_name"],
            field_value=data.get("field_value", ""),
            sensitivity_weight=int(data.get("sensitivity_weight", 1)),
            detection_method=data.get("detection_method", "regex"),
            confidence=float(data.get("confidence", 0.0)),
            bounding_box=BoundingBox(
                x=int(bbox.get("x", 0)),
                y=int(bbox.get("y", 0)),
                width=int(bbox.get("width", 0)),
                height=int(bbox.get("height", 0)),
            ),
            explanation=data.get("explanation", ""),
            required=bool(data.get("required", False)),
            redaction_decision=data.get("redaction_decision", "redact"),
            metadata=data.get("metadata", {}),
        )
