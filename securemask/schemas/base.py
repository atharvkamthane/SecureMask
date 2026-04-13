"""Base schema dataclass for field definitions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldSchema:
    field_name: str
    sensitivity_weight: int  # 1-10
    extraction_method: str  # "regex_fuzzy", "ner", "mrz", "qr", "image", "qr_primary_regex_fallback", etc.
    regex_pattern: str | None = None
    fuzzy_threshold: int = 80  # 0-100, rapidfuzz cutoff
    anchor_keywords: list[str] = field(default_factory=list)
    zone: str = "anywhere"  # "top" | "middle" | "bottom" | "anywhere"
    always_redact: bool = False

    # Legacy compat
    @property
    def regex(self) -> str | None:
        return self.regex_pattern

    @property
    def keywords(self) -> list[str]:
        return self.anchor_keywords
