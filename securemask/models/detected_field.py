from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BoundingBox:
    x: int | float
    y: int | float
    width: int | float
    height: int | float

    def padded(self, padding: int, max_width: int, max_height: int) -> "BoundingBox":
        x = max(0, int(self.x) - padding)
        y = max(0, int(self.y) - padding)
        right = min(max_width, int(self.x) + int(self.width) + padding)
        bottom = min(max_height, int(self.y) + int(self.height) + padding)
        return BoundingBox(x=x, y=y, width=max(0, right - x), height=max(0, bottom - y))

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (int(self.x), int(self.y), int(self.x) + int(self.width), int(self.y) + int(self.height))


@dataclass
class DetectedField:
    field_name: str
    field_value: str
    sensitivity_weight: int
    detection_method: str  # qr | mrz | regex_fuzzy | ner | image
    confidence: float
    bounding_box: BoundingBox
    needs_review: bool = False  # confidence < 0.70
    always_redact: bool = False
    explanation: str = ""
    required: bool = False  # set by necessity classifier
    redaction_decision: str = "redact"
    metadata: dict[str, Any] = field(default_factory=dict)
    bounding_box_pct: BoundingBox | None = None  # percentage-based for frontend overlays

    def __post_init__(self):
        if self.confidence < 0.70:
            self.needs_review = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("metadata", None)
        if self.bounding_box_pct:
            data["bounding_box_pct"] = asdict(self.bounding_box_pct)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DetectedField":
        bbox = data.get("bounding_box") or {}
        bbox_pct = data.get("bounding_box_pct")
        pct_box = None
        if bbox_pct:
            pct_box = BoundingBox(
                x=float(bbox_pct.get("x", 0)),
                y=float(bbox_pct.get("y", 0)),
                width=float(bbox_pct.get("width", 0)),
                height=float(bbox_pct.get("height", 0)),
            )
        return cls(
            field_name=data["field_name"],
            field_value=data.get("field_value", ""),
            sensitivity_weight=int(data.get("sensitivity_weight", 1)),
            detection_method=data.get("detection_method", "regex_fuzzy"),
            confidence=float(data.get("confidence", 0.0)),
            bounding_box=BoundingBox(
                x=int(float(bbox.get("x", 0))),
                y=int(float(bbox.get("y", 0))),
                width=int(float(bbox.get("width", 0))),
                height=int(float(bbox.get("height", 0))),
            ),
            needs_review=bool(data.get("needs_review", False)),
            always_redact=bool(data.get("always_redact", False)),
            explanation=data.get("explanation", ""),
            required=bool(data.get("required", False)),
            redaction_decision=data.get("redaction_decision", "redact"),
            metadata=data.get("metadata", {}),
            bounding_box_pct=pct_box,
        )
