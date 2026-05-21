"""Fuzzy regex extractor using rapidfuzz.

Handles OCR character errors (7→T, 0→O, 1→l) through approximate matching.
Strategy:
  1. Clean OCR text (correct common digit/letter substitutions)
  2. Exact regex on cleaned text → accept all matches, use proximity only to RANK
  3. Sliding-window fuzzy match on word tokens
  4. Keyword-anchored local search

Key bug fixed vs previous version:
  The old code had `if not anchor_keywords or best_prox_score > 0.15` which
  REJECTED valid regex matches when the value was far from the anchor keyword
  in linearized text (e.g. Aadhaar number at bottom, "aadhaar" label at top).
  Proximity now only ranks multiple matches — never blocks a single clean hit.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date as _date

from rapidfuzz import fuzz

from securemask.core.ocr import OCRWord
from securemask.models.detected_field import BoundingBox


# ------------------------------------------------------------------
# OCR noise correction tables
# ------------------------------------------------------------------

# Characters that look like digits but aren't — applied before digit-pattern regex
_DIGIT_CONFUSION_CLEAN = str.maketrans({
    'O': '0', 'o': '0',   # letter O → zero
    'I': '1', 'l': '1',   # capital I / lowercase l → one
    'S': '5',              # S → 5 (common in IDs)
    'B': '8',              # B → 8
    'Z': '2',              # Z → 2
    'G': '6',              # G → 6 (less common but seen)
    'Q': '0',              # Q → 0
    'D': '0',              # D → 0 (rare but seen with EasyOCR)
})

# Characters that look like letters — applied only in alpha-pattern contexts
_ALPHA_CONFUSION_CLEAN = str.maketrans({
    '0': 'O',
    '1': 'I',
    '5': 'S',
    '8': 'B',
})


def _clean_for_digits(text: str) -> str:
    """Replace letter-lookalikes with their digit equivalents.

    Only replaces inside groups that are predominantly numeric
    (≥50% of adjacent chars are real digits) to avoid corrupting pure text.
    """
    # Token-by-token: only clean tokens that look mostly numeric
    def _clean_token(tok: str) -> str:
        digit_count = sum(1 for c in tok if c.isdigit())
        if digit_count >= len(tok) * 0.4:  # at least 40% already digits
            return tok.translate(_DIGIT_CONFUSION_CLEAN)
        return tok

    return re.sub(r'[\w]+', lambda m: _clean_token(m.group()), text)


def _validate_date_year(value: str) -> bool:
    """Return True if value contains no 4-digit year, or has a plausible one."""
    four_digit_nums = re.findall(r'\b(\d{4})\b', value)
    if not four_digit_nums:
        return True
    current_year = _date.today().year
    return any(1900 <= int(y) <= current_year for y in four_digit_nums)


@dataclass
class FuzzyCandidate:
    text: str
    bbox: BoundingBox
    words: list[OCRWord]


class FuzzyRegexExtractor:
    """Extract field values using regex with fuzzy fallback."""

    # ------------------------------------------------------------------
    # Proximity helpers — used to RANK matches, not to reject them
    # ------------------------------------------------------------------

    def _proximity_score(self, match_start: int, match_end: int,
                          text: str, anchor_keywords: list[str]) -> float:
        """Score [0..1+] based on distance to nearest anchor keyword in text.

        Higher = closer to a relevant label. Used to pick the best of
        MULTIPLE regex matches, never to discard a lone match.
        """
        if not anchor_keywords:
            return 1.0

        text_lower = text.lower()
        min_dist = float('inf')
        best_bonus = 1.0

        for kw in anchor_keywords:
            for m in re.finditer(re.escape(kw.lower()), text_lower):
                if m.end() <= match_start:
                    dist = match_start - m.end()
                    bonus = 1.2  # label before value is most common
                elif match_end <= m.start():
                    dist = m.start() - match_end
                    bonus = 0.9
                else:
                    dist = 0
                    bonus = 1.5
                if dist < min_dist:
                    min_dist = dist
                    best_bonus = bonus

        if min_dist == float('inf'):
            # No anchor found in text at all — still accept the match
            return 0.5

        return math.exp(-min_dist / 80.0) * best_bonus

    def _word_proximity_score(self, words: list[OCRWord],
                               start_idx: int, end_idx: int,
                               anchor_keywords: list[str]) -> float:
        if not anchor_keywords:
            return 1.0
        min_dist = float('inf')
        for idx, w in enumerate(words):
            w_lower = w.text.lower()
            for kw in anchor_keywords:
                if kw.lower() in w_lower or w_lower in kw.lower():
                    dist = max(0, start_idx - idx) if idx < start_idx \
                        else max(0, idx - end_idx) if idx > end_idx else 0
                    min_dist = min(min_dist, dist)
        if min_dist == float('inf'):
            return 0.5
        return math.exp(-min_dist / 15.0)

    # ------------------------------------------------------------------
    # Public extract
    # ------------------------------------------------------------------

    def extract(
        self,
        text: str,
        pattern: str,
        threshold: int,
        words: list[OCRWord],
        anchor_keywords: list[str],
    ) -> tuple[str | None, float, BoundingBox | None]:
        """Extract a field value matching pattern.

        Returns (value, confidence, bounding_box) or (None, 0.0, None).
        """
        # Build a noise-corrected copy for digit patterns
        cleaned_text = _clean_for_digits(text)

        # ---- Step 1: exact regex (try both raw and cleaned text) ----
        result = self._exact_regex(text, pattern, anchor_keywords, words)
        if result[0] is None and cleaned_text != text:
            result = self._exact_regex(cleaned_text, pattern, anchor_keywords, words)
            if result[0]:
                # Map bbox back using original words (positions unchanged)
                val, conf, _ = result
                bbox = self._find_bbox(val, words)
                return val, conf, bbox
        if result[0]:
            return result

        # ---- Step 2: sliding-window fuzzy match ----
        result = self._fuzzy_window(text, pattern, threshold, words, anchor_keywords)
        if result[0]:
            return result

        # ---- Step 3: keyword-anchored local search ----
        return self._keyword_anchor_extract(text, words, anchor_keywords, pattern)

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _exact_regex(
        self,
        text: str,
        pattern: str,
        anchor_keywords: list[str],
        words: list[OCRWord],
    ) -> tuple[str | None, float, BoundingBox | None]:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            return None, 0.0, None

        best_val: str | None = None
        best_score = -1.0

        for m in matches:
            # Extract value (handle optional capture groups)
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

            # Reject implausible dates only when the match actually looks date-like.
            # This avoids false negatives for Aadhaar/PAN values that happen to
            # contain 4-digit groups but are not dates.
            anchor_context = " ".join(anchor_keywords).lower()
            looks_date_like = bool(re.search(r"[\/\-.]", val)) or any(
                term in anchor_context for term in ("dob", "date", "birth", "yob")
            )
            if looks_date_like and not _validate_date_year(val):
                continue

            # Proximity score used only to RANK multiple matches
            prox = self._proximity_score(m.start(), m.end(), text, anchor_keywords)
            if prox > best_score:
                best_score = prox
                best_val = val

        if best_val is None:
            return None, 0.0, None

        bbox = self._find_bbox(best_val, words)
        # Confidence: high base for exact pattern hit; proximity adds small bonus
        # No proximity GATE — a lone clean pattern match is always accepted
        conf = min(0.88 + best_score * 0.10, 0.98)
        return best_val, conf, bbox

    def _fuzzy_window(
        self,
        text: str,
        pattern: str,
        threshold: int,
        words: list[OCRWord],
        anchor_keywords: list[str],
    ) -> tuple[str | None, float, BoundingBox | None]:
        candidates = self._sliding_window_candidates(words)
        template = self._generate_template(pattern)

        best_candidate = None
        best_score = 0.0

        for candidate in candidates:
            cleaned = re.sub(r'\s+', '', candidate.text)
            if not cleaned:
                continue
            ratio = fuzz.ratio(cleaned, template)
            if ratio <= threshold:
                continue

            start_idx = end_idx = 0
            if candidate.words:
                try:
                    start_idx = words.index(candidate.words[0])
                    end_idx   = words.index(candidate.words[-1])
                except ValueError:
                    pass

            prox  = self._word_proximity_score(words, start_idx, end_idx, anchor_keywords)
            score = ratio * 0.75 + prox * 25.0
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate:
            raw = fuzz.ratio(re.sub(r'\s+', '', best_candidate.text), template)
            if raw > threshold:
                return best_candidate.text, raw / 100, best_candidate.bbox

        return None, 0.0, None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sliding_window_candidates(self, words: list[OCRWord]) -> list[FuzzyCandidate]:
        """Generate candidates by joining 1–5 consecutive OCR words."""
        candidates = []
        for win in range(1, min(6, len(words) + 1)):
            for i in range(len(words) - win + 1):
                group = words[i: i + win]
                txt   = ' '.join(w.text for w in group)
                left   = min(w.bbox.x for w in group)
                top    = min(w.bbox.y for w in group)
                right  = max(w.bbox.x + w.bbox.width  for w in group)
                bottom = max(w.bbox.y + w.bbox.height for w in group)
                candidates.append(FuzzyCandidate(
                    text=txt,
                    bbox=BoundingBox(left, top, right - left, bottom - top),
                    words=group,
                ))
        return candidates

    def _generate_template(self, pattern: str) -> str:
        """Convert regex to a representative sample string for fuzzy matching."""
        t = pattern
        t = re.sub(r'\\b', '', t)
        t = re.sub(r'\\d\{(\d+)\}',     lambda m: '0' * int(m.group(1)), t)
        t = re.sub(r'\\d\{(\d+),(\d+)\}', lambda m: '0' * int(m.group(2)), t)
        t = re.sub(r'\\d', '0', t)
        t = re.sub(r'\[A-Z\]\{(\d+)\}', lambda m: 'A' * int(m.group(1)), t)
        t = re.sub(r'\[A-Z\]', 'A', t)
        t = re.sub(r'\[A-Za-z\]', 'A', t)
        t = re.sub(r'\\s\?', ' ', t)
        t = re.sub(r'\\s\+', ' ', t)
        t = re.sub(r'[\(\)\[\]\{\}\?\*\+\|]', '', t)
        t = re.sub(r'\\[\/\-\.]', '/', t)
        return t.strip()

    def _find_bbox(self, value: str, words: list[OCRWord]) -> BoundingBox:
        from securemask.utils.bbox_utils import find_bbox_in_words
        return find_bbox_in_words(value, words)

    def _keyword_anchor_extract(
        self,
        text: str,
        words: list[OCRWord],
        keywords: list[str],
        pattern: str,
    ) -> tuple[str | None, float, BoundingBox | None]:
        """Find anchor keyword, search nearby text for pattern match."""
        text_lower = text.lower()
        # Search window: 120 chars after keyword (was 60 — too short for multi-line)
        WINDOW = 120
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx >= 0:
                after = text[idx + len(kw):].strip().lstrip(':').strip()
                m = re.search(pattern, after[:WINDOW], re.IGNORECASE)
                if m:
                    val  = m.group()
                    bbox = self._find_bbox(val, words)
                    return val, 0.80, bbox
        return None, 0.0, None