"""Fuzzy regex extractor using rapidfuzz.

Handles OCR character errors (7→T, 0→O, 1→l) through approximate matching.
Strategy: exact regex → sliding-window fuzzy match → keyword-anchored search.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from securemask.core.ocr import OCRWord
from securemask.models.detected_field import BoundingBox


@dataclass
class FuzzyCandidate:
    text: str
    bbox: BoundingBox
    words: list[OCRWord]


class FuzzyRegexExtractor:
    """Extract field values using regex with fuzzy fallback."""

    def extract(self, text: str, pattern: str, threshold: int,
                words: list[OCRWord], anchor_keywords: list[str]
                ) -> tuple[str | None, float, BoundingBox | None]:
        """Try to extract a value matching the pattern.

        Returns (value, confidence, bounding_box) or (None, 0.0, None).
        """
        # Step 1: Try exact regex
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group()
            bbox = self._find_bbox(value, words)
            return value, 0.95, bbox

        # Step 2: Sliding window fuzzy match on OCR words
        candidates = self._sliding_window_candidates(words)
        template = self._generate_template(pattern)

        best_match = None
        best_score = 0.0

        for candidate in candidates:
            cleaned = re.sub(r"\s+", "", candidate.text)
            if not cleaned:
                continue
            score = fuzz.ratio(cleaned, template)
            if score > threshold and score > best_score:
                best_match = candidate
                best_score = score

        if best_match and best_score > threshold:
            return best_match.text, best_score / 100, best_match.bbox

        # Step 3: Keyword-anchored search
        return self._keyword_anchor_extract(text, words, anchor_keywords, pattern)

    def _sliding_window_candidates(self, words: list[OCRWord]) -> list[FuzzyCandidate]:
        """Generate candidates by joining 1-5 consecutive OCR words."""
        candidates = []
        for window_size in range(1, min(6, len(words) + 1)):
            for i in range(len(words) - window_size + 1):
                group = words[i: i + window_size]
                text = " ".join(w.text for w in group)
                left = min(w.bbox.x for w in group)
                top = min(w.bbox.y for w in group)
                right = max(w.bbox.x + w.bbox.width for w in group)
                bottom = max(w.bbox.y + w.bbox.height for w in group)
                candidates.append(FuzzyCandidate(
                    text=text,
                    bbox=BoundingBox(left, top, right - left, bottom - top),
                    words=group,
                ))
        return candidates

    def _generate_template(self, pattern: str) -> str:
        """Convert a regex pattern to a representative template for fuzzy matching."""
        # Replace common pattern elements with sample characters
        template = pattern
        template = re.sub(r"\\b", "", template)
        template = re.sub(r"\\d\{(\d+)\}", lambda m: "0" * int(m.group(1)), template)
        template = re.sub(r"\\d\{(\d+),(\d+)\}", lambda m: "0" * int(m.group(2)), template)
        template = re.sub(r"\\d", "0", template)
        template = re.sub(r"\[A-Z\]\{(\d+)\}", lambda m: "A" * int(m.group(1)), template)
        template = re.sub(r"\[A-Z\]", "A", template)
        template = re.sub(r"\[A-Za-z\]", "A", template)
        template = re.sub(r"\\s\?", " ", template)
        template = re.sub(r"\\s\+", " ", template)
        template = re.sub(r"[\(\)\[\]\{\}\?\*\+\|]", "", template)
        template = re.sub(r"\\[\/\-\.]", "/", template)
        return template.strip()

    def _find_bbox(self, value: str, words: list[OCRWord]) -> BoundingBox:
        """Find bounding box for a matched value among OCR words."""
        value_parts = [p for p in re.findall(r"\w+", value.lower()) if len(p) >= 2]
        if not value_parts:
            value_parts = [value.lower().strip()]
            
        matched = []
        for w in words:
            w_clean = re.sub(r"\W+", "", w.text).lower()
            if not w_clean:
                continue
            # If OCR word overlaps significantly with any value part
            if any(w_clean in p or p in w_clean for p in value_parts):
                matched.append(w)
                
        if matched:
            left = min(w.bbox.x for w in matched)
            top = min(w.bbox.y for w in matched)
            right = max(w.bbox.x + w.bbox.width for w in matched)
            bottom = max(w.bbox.y + w.bbox.height for w in matched)
            return BoundingBox(left, top, right - left, bottom - top)
        
        # If absolutely nothing matched, fallback to a small box (which unfortunately means no visual redaction)
        return BoundingBox(0, 0, 1, 1)

    def _keyword_anchor_extract(self, text: str, words: list[OCRWord],
                                 keywords: list[str], pattern: str
                                 ) -> tuple[str | None, float, BoundingBox | None]:
        """Find anchor keyword, extract value from nearby text, validate with pattern."""
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx >= 0:
                # Extract text after the keyword
                after = text[idx + len(kw):].strip().lstrip(":").strip()
                match = re.search(pattern, after, re.IGNORECASE)
                if match:
                    value = match.group()
                    bbox = self._find_bbox(value, words)
                    return value, 0.82, bbox
        return None, 0.0, None
