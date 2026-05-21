"""Bounding box calculation utilities."""
from __future__ import annotations

import re
from rapidfuzz import fuzz
from securemask.core.ocr import OCRWord
from securemask.models.detected_field import BoundingBox

def find_bbox_in_words(value: str, words: list[OCRWord]) -> BoundingBox:
    """Find the best contiguous sequence of OCR words that matches the target value."""
    if not words or not value:
        return BoundingBox(0, 0, 1, 1)
        
    # Clean the target value and get its word list
    target_clean = re.sub(r"\W+", "", value).lower()
    target_words = [re.sub(r"\W+", "", w).lower() for w in re.findall(r"\w+", value.lower()) if re.sub(r"\W+", "", w).lower()]
    if not target_words:
        target_words = [value.lower().strip()]
        
    # Clean the OCR words
    ocr_clean = [re.sub(r"\W+", "", w.text).lower() for w in words]
    
    best_match_words = []
    best_score = 0.0
    
    n = len(words)
    target_len = len(target_words)
    
    # We allow window sizes from 1 up to target_len + 2
    min_win = 1
    max_win = target_len + 2
    
    for win_size in range(min_win, min(max_win + 1, n + 1)):
        for i in range(n - win_size + 1):
            sub_words = words[i:i+win_size]
            sub_clean_words = ocr_clean[i:i+win_size]
            
            # Combine the texts
            sub_combined = "".join(sub_clean_words)
            
            score = fuzz.ratio(sub_combined, target_clean)

            # Prefer longer windows on tie when value has multiple tokens (full UID/name)
            if score > best_score:
                best_score = score
                best_match_words = sub_words
            elif score == best_score and len(sub_words) > len(best_match_words):
                best_score = score
                best_match_words = sub_words
                
    if best_score > 60.0 and best_match_words:
        left = min(w.bbox.x for w in best_match_words)
        top = min(w.bbox.y for w in best_match_words)
        right = max(w.bbox.x + w.bbox.width for w in best_match_words)
        bottom = max(w.bbox.y + w.bbox.height for w in best_match_words)
        return BoundingBox(left, top, right - left, bottom - top)
        
    # Fallback: find the single word with the highest similarity
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


def expand_digit_sequence_bbox(value: str, words: list[OCRWord]) -> BoundingBox | None:
    """Union all 4-digit OCR tokens on the same row as a 12-digit UID value."""
    groups = re.findall(r"\d{4}", re.sub(r"\D", " ", value))
    if len(groups) < 2:
        return None

    seed = find_bbox_in_words(groups[0], words)
    if seed.width <= 2:
        return None

    row_y = seed.y + seed.height / 2
    row_h = max(seed.height, 20)
    boxes: list[BoundingBox] = [seed]
    for w in words:
        if not re.fullmatch(r"\d{3,4}", re.sub(r"\D", "", w.text)):
            continue
        cy = w.bbox.y + w.bbox.height / 2
        if abs(cy - row_y) <= row_h * 1.2:
            boxes.append(w.bbox)

    if len(boxes) < 2:
        return None

    left = min(b.x for b in boxes)
    top = min(b.y for b in boxes)
    right = max(b.x + b.width for b in boxes)
    bottom = max(b.y + b.height for b in boxes)
    return BoundingBox(left, top, right - left, bottom - top)
