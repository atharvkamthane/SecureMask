"""Fuzzy regex extractor using rapidfuzz.

Handles OCR character errors (7→T, 0→O, 1→l) through approximate matching.
Strategy: exact regex → sliding-window fuzzy match → keyword-anchored search.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date as _date

from rapidfuzz import fuzz

from securemask.core.ocr import OCRWord
from securemask.models.detected_field import BoundingBox


def _validate_date_year(value: str) -> bool:
    """Return True if the value contains no 4-digit year, or has one in a plausible range.

    Rejects dates like 99/99/9999 where the year is clearly an OCR artifact.
    """
    four_digit_nums = re.findall(r"\b(\d{4})\b", value)
    if not four_digit_nums:
        return True  # no 4-digit number to validate, pass through
    current_year = _date.today().year
    # Accept if at least one looks like a plausible year
    return any(1900 <= int(y) <= current_year for y in four_digit_nums)


@dataclass
class FuzzyCandidate:
    text: str
    bbox: BoundingBox
    words: list[OCRWord]


class FuzzyRegexExtractor:
    """Extract field values using regex with fuzzy fallback."""

    def _calculate_proximity_score(self, match_start: int, match_end: int, text: str, anchor_keywords: list[str]) -> float:
        import math
        if not anchor_keywords:
            return 1.0
            
        text_lower = text.lower()
        min_dist = float('inf')
        best_dir_bonus = 1.0
        
        for kw in anchor_keywords:
            kw_lower = kw.lower()
            for kw_match in re.finditer(re.escape(kw_lower), text_lower):
                kw_start = kw_match.start()
                kw_end = kw_match.end()
                
                if kw_end <= match_start:
                    dist = match_start - kw_end
                    direction_bonus = 1.2  # favor labels preceding values
                elif match_end <= kw_start:
                    dist = kw_start - match_end
                    direction_bonus = 0.8  # slightly penalize labels succeeding values
                else:
                    dist = 0
                    direction_bonus = 1.5
                    
                if dist < min_dist:
                    min_dist = dist
                    best_dir_bonus = direction_bonus
                    
        if min_dist == float('inf'):
            return 0.0
            
        return math.exp(-min_dist / 60.0) * best_dir_bonus

    def _word_proximity_score(self, words: list[OCRWord], candidate_start_idx: int, candidate_end_idx: int, anchor_keywords: list[str]) -> float:
        import math
        if not anchor_keywords:
            return 1.0
            
        min_dist = float('inf')
        for idx, w in enumerate(words):
            w_lower = w.text.lower()
            for kw in anchor_keywords:
                if kw.lower() in w_lower or w_lower in kw.lower():
                    if idx < candidate_start_idx:
                        dist = candidate_start_idx - idx
                    elif idx > candidate_end_idx:
                        dist = idx - candidate_end_idx
                    else:
                        dist = 0
                    if dist < min_dist:
                        min_dist = dist
                        
        if min_dist == float('inf'):
            return 0.0
            
        return math.exp(-min_dist / 12.0)

    def extract(self, text: str, pattern: str, threshold: int,
                words: list[OCRWord], anchor_keywords: list[str]
                ) -> tuple[str | None, float, BoundingBox | None]:
        """Try to extract a value matching the pattern.

        Returns (value, confidence, bounding_box) or (None, 0.0, None).
        """
        # Step 1: Try exact regex with proximity ranking
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            best_match_val = None
            best_prox_score = -1.0
            
            for m in matches:
                if m.lastindex and m.lastindex >= 3:
                    try:
                        val = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
                    except IndexError:
                        val = m.group()
                elif m.lastindex and m.lastindex >= 1:
                    val = m.group(1)
                else:
                    val = m.group()
                val = val.strip()
                
                prox_score = self._calculate_proximity_score(m.start(), m.end(), text, anchor_keywords)
                if prox_score > best_prox_score:
                    best_prox_score = prox_score
                    best_match_val = val

            if best_match_val and (not anchor_keywords or best_prox_score > 0.15):
                # Reject dates with implausible years (OCR artifacts / boilerplate)
                if not _validate_date_year(best_match_val):
                    best_match_val = None
            if best_match_val:
                bbox = self._find_bbox(best_match_val, words)
                confidence = 0.95 if not anchor_keywords else min(0.70 + best_prox_score * 0.28, 0.98)
                return best_match_val, confidence, bbox

        # Step 2: Sliding window fuzzy match on OCR words
        candidates = self._sliding_window_candidates(words)
        template = self._generate_template(pattern)

        best_candidate = None
        best_combined_score = 0.0
        best_prox = 1.0

        for candidate in candidates:
            cleaned = re.sub(r"\s+", "", candidate.text)
            if not cleaned:
                continue
            ratio = fuzz.ratio(cleaned, template)
            if ratio > threshold:
                # Find candidate index range in words
                start_idx = 0
                end_idx = 0
                if candidate.words:
                    try:
                        start_idx = words.index(candidate.words[0])
                        end_idx = words.index(candidate.words[-1])
                    except ValueError:
                        pass
                
                prox = self._word_proximity_score(words, start_idx, end_idx, anchor_keywords)
                combined = ratio * 0.7 + (prox * 30.0)
                if combined > best_combined_score:
                    best_candidate = candidate
                    best_combined_score = combined
                    best_prox = prox

        if best_candidate and (best_combined_score - 30.0 * (1.0 - best_prox if anchor_keywords else 0.0)) > threshold:
            raw_ratio = fuzz.ratio(re.sub(r"\s+", "", best_candidate.text), template)
            return best_candidate.text, raw_ratio / 100, best_candidate.bbox

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
        from securemask.utils.bbox_utils import find_bbox_in_words
        return find_bbox_in_words(value, words)

    def _keyword_anchor_extract(self, text: str, words: list[OCRWord],
                                 keywords: list[str], pattern: str
                                 ) -> tuple[str | None, float, BoundingBox | None]:
        """Find anchor keyword, extract value from nearby text, validate with pattern."""
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx >= 0:
                # Extract text after the keyword and restrict it to nearby region
                after = text[idx + len(kw):].strip().lstrip(":").strip()
                match = re.search(pattern, after[:60], re.IGNORECASE)
                if match:
                    value = match.group()
                    bbox = self._find_bbox(value, words)
                    return value, 0.82, bbox
        return None, 0.0, None
