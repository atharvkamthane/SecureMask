"""Bounding box calculation utilities."""
from __future__ import annotations

import re
from rapidfuzz import fuzz
from securemask.core.ocr import OCRWord
from securemask.models.detected_field import BoundingBox

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text))


def clamp_bbox_sanity(
    box: BoundingBox,
    img_w: int,
    img_h: int,
    *,
    max_w_pct: float = 0.5,
    max_h_pct: float = 0.25,
) -> BoundingBox | None:
    """Reject boxes that cover too much of the image (OCR line-overmatch)."""
    if img_w <= 0 or img_h <= 0:
        return box
    if box.width > img_w * max_w_pct or box.height > img_h * max_h_pct:
        return None
    if box.width <= 1 or box.height <= 1:
        return None
    return box


def find_bbox_in_words(
    value: str,
    words: list[OCRWord],
    *,
    max_window: int | None = None,
    prefer_short: bool = True,
) -> BoundingBox:
    """Find the best contiguous sequence of OCR words that matches the target value."""
    if not words or not value:
        return BoundingBox(0, 0, 1, 1)

    target_clean = re.sub(r"\W+", "", value).lower()
    target_words = [
        re.sub(r"\W+", "", w).lower()
        for w in re.findall(r"\w+", value.lower())
        if re.sub(r"\W+", "", w).lower()
    ]
    if not target_words:
        target_words = [value.lower().strip()]

    ocr_clean = [re.sub(r"\W+", "", w.text).lower() for w in words]

    best_match_words: list[OCRWord] = []
    best_score = 0.0

    n = len(words)
    target_len = len(target_words)
    min_win = 1
    cap = max_window if max_window is not None else min(target_len + 1, 8)
    max_win = min(cap, n)

    for win_size in range(min_win, max_win + 1):
        for i in range(n - win_size + 1):
            sub_words = words[i : i + win_size]
            sub_clean_words = ocr_clean[i : i + win_size]
            sub_combined = "".join(sub_clean_words)
            score = fuzz.ratio(sub_combined, target_clean)

            if score > best_score:
                best_score = score
                best_match_words = sub_words
            elif score == best_score and best_match_words:
                if prefer_short and len(sub_words) < len(best_match_words):
                    best_match_words = sub_words
                elif not prefer_short and len(sub_words) > len(best_match_words):
                    best_match_words = sub_words

    if best_score > 60.0 and best_match_words:
        left = min(w.bbox.x for w in best_match_words)
        top = min(w.bbox.y for w in best_match_words)
        right = max(w.bbox.x + w.bbox.width for w in best_match_words)
        bottom = max(w.bbox.y + w.bbox.height for w in best_match_words)
        return BoundingBox(left, top, right - left, bottom - top)

    best_single_word = None
    best_single_score = 0.0
    for w in words:
        w_clean = re.sub(r"\W+", "", w.text).lower()
        if not w_clean:
            continue
        score = fuzz.ratio(w_clean, target_clean)
        if score > best_single_score:
            best_single_score = score
            best_single_word = w

    if best_single_score > 50.0 and best_single_word:
        return best_single_word.bbox

    return BoundingBox(0, 0, 1, 1)


def find_date_digits_bbox(date_value: str, words: list[OCRWord]) -> BoundingBox | None:
    """Union only digit tokens that form the date (not the full DOB label line)."""
    m = re.search(
        r"(\d{1,2})[\s\/\-\.\+oO+]{0,4}(\d{1,2})[\s\/\-\.\+oO+]{0,4}(\d{4})",
        date_value,
    )
    if not m:
        return find_bbox_in_words(date_value, words, max_window=4)

    parts = [m.group(1), m.group(2), m.group(3)]
    hits: list[OCRWord] = []
    for part in parts:
        part_digits = re.sub(r"\D", "", part)
        if not part_digits:
            continue
        best_w: OCRWord | None = None
        best_score = 0.0
        for w in words:
            w_digits = re.sub(r"\D", "", w.text)
            if not w_digits:
                continue
            score = fuzz.ratio(w_digits, part_digits)
            if score >= 75 and score > best_score:
                best_score = score
                best_w = w
        if best_w:
            hits.append(best_w)

    if len(hits) < 2:
        return find_bbox_in_words("/".join(parts), words, max_window=4)

    left = min(w.bbox.x for w in hits)
    top = min(w.bbox.y for w in hits)
    right = max(w.bbox.x + w.bbox.width for w in hits)
    bottom = max(w.bbox.y + w.bbox.height for w in hits)
    return BoundingBox(left, top, right - left, bottom - top)


def find_devanagari_bbox(text: str, words: list[OCRWord]) -> BoundingBox | None:
    """BBox for a Devanagari name from words that contain the script."""
    tokens = [t for t in text.split() if has_devanagari(t) and len(t) >= 2]
    if not tokens:
        return None
    hits: list[OCRWord] = []
    for token in tokens:
        for w in words:
            if has_devanagari(w.text) and fuzz.partial_ratio(token, w.text) >= 70:
                hits.append(w)
                break
    if not hits:
        return find_bbox_in_words(tokens[0], words, max_window=min(len(tokens) + 1, 6))
    left = min(w.bbox.x for w in hits)
    top = min(w.bbox.y for w in hits)
    right = max(w.bbox.x + w.bbox.width for w in hits)
    bottom = max(w.bbox.y + w.bbox.height for w in hits)
    return BoundingBox(left, top, right - left, bottom - top)


def expand_digit_sequence_bbox(
    value: str,
    words: list[OCRWord],
    *,
    image_height: int = 0,
    image_width: int = 0,
) -> BoundingBox | None:
    """Union 4-digit OCR tokens on the UID row (bottom of card, x-proximity)."""
    groups = re.findall(r"\d{4}", re.sub(r"\D", " ", value))
    if len(groups) < 2:
        return None

    bottom_cut = int(image_height * 0.75) if image_height > 0 else 0

    def _in_zone(w: OCRWord) -> bool:
        if image_height > 0 and (w.bbox.y + w.bbox.height / 2) < bottom_cut:
            return False
        return True

    digit_words = [
        w for w in words
        if _in_zone(w) and re.fullmatch(r"\d{3,4}", re.sub(r"\D", "", w.text))
    ]
    if len(digit_words) < 2:
        return None

    seed = find_bbox_in_words(groups[0], digit_words, max_window=1)
    if seed.width <= 2:
        return None

    row_y = seed.y + seed.height / 2
    row_h = max(seed.height, 20)
    max_x_gap = max(image_width * 0.35, 280) if image_width > 0 else 320
    boxes: list[BoundingBox] = [seed]

    for w in digit_words:
        cy = w.bbox.y + w.bbox.height / 2
        if abs(cy - row_y) > row_h * 1.2:
            continue
        cx = w.bbox.x + w.bbox.width / 2
        seed_cx = seed.x + seed.width / 2
        if abs(cx - seed_cx) > max_x_gap:
            continue
        boxes.append(w.bbox)

    if len(boxes) < 2:
        return None

    left = min(b.x for b in boxes)
    top = min(b.y for b in boxes)
    right = max(b.x + b.width for b in boxes)
    bottom = max(b.y + b.height for b in boxes)
    return BoundingBox(left, top, right - left, bottom - top)
