"""NER extractor using HuggingFace models for Indian-language text.

Model priority: ai4bharat/IndicNER → spaCy en_core_web_sm fallback.
Entity types: PER (person), LOC (location), ORG (organization), DATE.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache

from securemask.core.ocr import OCRWord
from securemask.models.detected_field import BoundingBox

logger = logging.getLogger(__name__)

# Entity → field name mapping
ENTITY_FIELD_MAP = {
    "PER": ["name", "father_name", "father_husband_name", "father_spouse_name"],
    "LOC": ["address", "place_of_birth", "place_of_issue"],
    "GPE": ["address", "place_of_birth"],
    "ORG": ["employer_name"],
    "DATE": ["dob", "date_of_expiry"],
    "PERSON": ["name", "father_name", "father_husband_name", "father_spouse_name"],
    "LOCATION": ["address", "place_of_birth"],
}

# Words that should never be extracted as a person name
NAME_BLACKLIST = {
    "government", "india", "uidai", "aadhaar", "unique", "identification",
    "authority", "proof", "identity", "citizenship", "verification",
    "republic", "income", "tax", "department", "permanent", "account",
    "election", "commission", "transport", "passport", "driving", "licence",
    "license", "elector", "voter", "male", "female",
    "भारत", "सरकार", "आधार",
}


def _is_blacklisted_name(text: str) -> bool:
    words = set(re.findall(r"\w+", text.lower()))
    overlap = words & NAME_BLACKLIST
    return len(words) > 0 and len(overlap) / len(words) > 0.3


@lru_cache(maxsize=1)
def _load_hf_pipeline():
    """Try loading a HuggingFace NER pipeline."""
    try:
        from transformers import pipeline
        # Try IndicNER first
        try:
            ner = pipeline("token-classification", model="ai4bharat/IndicNER",
                           aggregation_strategy="simple", device=-1)
            logger.info("Loaded ai4bharat/IndicNER model")
            return ner, "indicner"
        except Exception:
            pass

        # Try xlm-roberta NER
        try:
            ner = pipeline("token-classification", model="xlm-roberta-base",
                           aggregation_strategy="simple", device=-1)
            logger.info("Loaded xlm-roberta-base for NER")
            return ner, "xlm-roberta"
        except Exception:
            pass
    except ImportError:
        pass
    return None, None


@lru_cache(maxsize=1)
def _load_spacy():
    """Fallback: spaCy English NER model."""
    try:
        import spacy
        model = spacy.load("en_core_web_sm")
        logger.info("Loaded spaCy en_core_web_sm for NER fallback")
        return model
    except Exception:
        try:
            import spacy
            return spacy.blank("en")
        except Exception:
            return None


def _find_bbox_for_text(text: str, words: list[OCRWord]) -> BoundingBox:
    """Find bounding box of matched text among OCR words."""
    text_parts = [p for p in re.findall(r"\w+", text.lower()) if len(p) >= 2]
    if not text_parts:
        text_parts = [text.lower().strip()]
        
    matched = []
    for w in words:
        w_clean = re.sub(r"\W+", "", w.text).lower()
        if not w_clean:
            continue
        # If OCR word overlaps significantly with any text part
        if any(w_clean in p or p in w_clean for p in text_parts):
            matched.append(w)
            
    if matched:
        left = min(w.bbox.x for w in matched)
        top = min(w.bbox.y for w in matched)
        right = max(w.bbox.x + w.bbox.width for w in matched)
        bottom = max(w.bbox.y + w.bbox.height for w in matched)
        return BoundingBox(left, top, right - left, bottom - top)
    return BoundingBox(0, 0, 1, 1)


def _keyword_proximity(entity_text: str, entity_start: int, text: str, keywords: list[str]) -> float:
    """Score based on proximity to anchor keywords in text."""
    text_lower = text.lower()
    best_dist = len(text)
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx >= 0:
            dist = abs(entity_start - idx)
            best_dist = min(best_dist, dist)
    return max(0, 1.0 - best_dist / max(len(text), 1))


class NERExtractor:
    """Named entity recognition extractor with HuggingFace + spaCy fallback."""

    def __init__(self):
        self._hf_pipe, self._hf_type = _load_hf_pipeline()
        self._spacy = _load_spacy()

    def extract(self, text: str, field_name: str, words: list[OCRWord],
                anchor_keywords: list[str]) -> tuple[str | None, float, BoundingBox | None]:
        """Extract a named entity matching the target field_name.

        Returns (value, confidence, bounding_box) or (None, 0.0, None).
        """
        # Determine target entity types
        target_types = set()
        for ent_type, fields in ENTITY_FIELD_MAP.items():
            if field_name in fields:
                target_types.add(ent_type)

        if not target_types:
            return None, 0.0, None

        # Try HuggingFace NER
        if self._hf_pipe is not None:
            result = self._hf_extract(text, field_name, target_types, words, anchor_keywords)
            if result[0]:
                return result

        # Spacy fallback
        if self._spacy is not None:
            result = self._spacy_extract(text, field_name, target_types, words, anchor_keywords)
            if result[0]:
                return result

        # Keyword anchored fallback
        return self._keyword_anchor(text, field_name, words, anchor_keywords)

    def _hf_extract(self, text, field_name, target_types, words, keywords):
        try:
            entities = self._hf_pipe(text)
            candidates = []
            for ent in entities:
                ent_group = ent.get("entity_group", "")
                if ent_group in target_types:
                    value = ent.get("word", "").strip()
                    if field_name in ("name", "father_name") and _is_blacklisted_name(value):
                        continue
                    score = ent.get("score", 0.5)
                    proximity = _keyword_proximity(value, ent.get("start", 0), text, keywords)
                    candidates.append((value, score * 0.7 + proximity * 0.3, ent))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                value, conf, _ = candidates[0]
                bbox = _find_bbox_for_text(value, words)
                return value, min(conf, 0.95), bbox
        except Exception as exc:
            logger.debug("HF NER failed: %s", exc)
        return None, 0.0, None

    def _spacy_extract(self, text, field_name, target_types, words, keywords):
        try:
            doc = self._spacy(text)
            candidates = []
            for ent in doc.ents:
                if ent.label_ in target_types:
                    if field_name in ("name", "father_name") and _is_blacklisted_name(ent.text):
                        continue
                    proximity = _keyword_proximity(ent.text, ent.start_char, text, keywords)
                    candidates.append((ent.text, 0.72 * 0.7 + proximity * 0.3))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                value, conf = candidates[0]
                bbox = _find_bbox_for_text(value, words)
                return value, conf, bbox
        except Exception as exc:
            logger.debug("spaCy NER failed: %s", exc)
        return None, 0.0, None

    def _keyword_anchor(self, text, field_name, words, keywords):
        """Find keyword anchor and extract value from nearby words."""
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw.lower())
            if idx >= 0:
                after = text[idx + len(kw):].strip().lstrip(":").strip()
                parts = after.split()[:5]
                # Filter skip words
                skip = {"name", "dob", "date", "of", "birth", "gender", "sex",
                        "address", "government", "india", "uid", "male", "female"}
                parts = [p for p in parts if p.lower() not in skip]
                if parts:
                    value = " ".join(parts)
                    if field_name in ("name", "father_name") and _is_blacklisted_name(value):
                        continue
                    bbox = _find_bbox_for_text(value, words)
                    return value, 0.55, bbox
        return None, 0.0, None
