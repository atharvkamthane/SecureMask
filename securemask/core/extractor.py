from __future__ import annotations

import re
from functools import lru_cache

from PIL import Image

from securemask.config import FieldSchema, UNIVERSAL_REGEX_PATTERNS
from securemask.core.explainer import explain_field
from securemask.core.ocr import OCRResult, OCRWord
from securemask.models.detected_field import BoundingBox, DetectedField
from securemask.schemas import SCHEMA_MODULES
from securemask.utils.image_utils import zone_bounds
from securemask.utils.qr_utils import detect_qr_codes


@lru_cache(maxsize=1)
def _load_spacy_model():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception:
        try:
            import spacy

            return spacy.blank("en")
        except Exception:
            return None


def _combine_boxes(words: list[OCRWord]) -> BoundingBox:
    if not words:
        return BoundingBox(0, 0, 1, 1)
    left = min(word.box.x for word in words)
    top = min(word.box.y for word in words)
    right = max(word.box.x + word.box.width for word in words)
    bottom = max(word.box.y + word.box.height for word in words)
    return BoundingBox(left, top, right - left, bottom - top)


def _words_in_zone(words: list[OCRWord], zone: str, image_height: int) -> list[OCRWord]:
    y_min, y_max = zone_bounds(zone, image_height)
    return [word for word in words if y_min <= word.box.y <= y_max]


def _bbox_for_value(value: str, words: list[OCRWord], zone: str, image_height: int) -> BoundingBox:
    zone_words = _words_in_zone(words, zone, image_height)
    value_parts = [part.lower() for part in re.findall(r"\w+", value)]
    compact_value = re.sub(r"\W+", "", value).lower()
    if value_parts:
        matched = [
            word
            for word in zone_words
            if re.sub(r"\W+", "", word.text).lower() in value_parts
            or re.sub(r"\W+", "", word.text).lower() == compact_value
        ]
        if matched:
            return _combine_boxes(matched[: max(len(value_parts), 1)])
    if zone_words:
        return _combine_boxes(zone_words[: min(8, len(zone_words))])
    all_matched = [
        word
        for word in words
        if re.sub(r"\W+", "", word.text).lower() in value_parts
        or re.sub(r"\W+", "", word.text).lower() == compact_value
    ]
    if all_matched:
        return _combine_boxes(all_matched[: max(len(value_parts), 1)])
    return BoundingBox(0, 0, 1, 1)


def _keyword_anchor_value(schema: FieldSchema, words: list[OCRWord], image_height: int) -> tuple[str, BoundingBox, str] | None:
    zone_words = _words_in_zone(words, schema.zone, image_height)
    lowered = [word.text.lower().strip(":") for word in zone_words]
    for keyword in schema.keywords:
        parts = keyword.lower().split()
        for index in range(len(lowered)):
            if lowered[index : index + len(parts)] == parts:
                value_words = zone_words[index + len(parts) : index + len(parts) + 5]
                value_words = [word for word in value_words if word.text.strip(":").lower() not in {"name", "dob", "date", "of", "birth"}]
                if value_words:
                    value = " ".join(word.text for word in value_words)
                    return value, _combine_boxes(value_words), keyword
    return None


def _ner_fields(text: str, words: list[OCRWord], image_height: int, schema: FieldSchema, document_type: str) -> list[DetectedField]:
    fields: list[DetectedField] = []
    model = _load_spacy_model()
    if model is not None and getattr(model, "pipe_names", []):
        doc = model(text)
        label_map = {"PERSON": "name", "GPE": "address", "LOC": "address", "ORG": "employer_name"}
        for entity in doc.ents:
            target = label_map.get(entity.label_)
            if target and (schema.field_name == target or schema.field_name in {"place_of_birth", "place_of_issue", "dispensary", "family_members", "head_of_family_name", "father_name", "father_husband_name", "father_name_spouse_name", "employer_name"}):
                field = DetectedField(schema.field_name, entity.text, schema.sensitivity_weight, "ner", 0.72, _bbox_for_value(entity.text, words, schema.zone, image_height), metadata={"entity_type": entity.label_})
                field.explanation = explain_field(field, document_type, schema)
                fields.append(field)
                break
    if fields:
        return fields
    anchored = _keyword_anchor_value(schema, words, image_height)
    if anchored:
        value, box, keyword = anchored
        field = DetectedField(schema.field_name, value, schema.sensitivity_weight, "keyword_anchor", 0.62, box, metadata={"matched_keyword": keyword})
        field.explanation = explain_field(field, document_type, schema)
        return [field]
    return []


def extract_fields(document_type: str, ocr: OCRResult, image_path: str | None = None) -> list[DetectedField]:
    if document_type == "unknown":
        return extract_unknown_fields(ocr)
    module = SCHEMA_MODULES[document_type]
    fields: list[DetectedField] = []
    seen: set[tuple[str, str]] = set()
    for schema in module.FIELDS:
        if schema.regex:
            zone_text = " ".join(word.text for word in _words_in_zone(ocr.words, schema.zone, ocr.image_height))
            haystack = ocr.text if schema.zone == "anywhere" else zone_text or ocr.text
            flags = re.IGNORECASE if schema.field_name in {"gender", "nationality", "category", "vehicle_class", "blood_group"} else 0
            for match in re.finditer(schema.regex, haystack, flags):
                value = match.group(0)
                key = (schema.field_name, value.lower())
                if key in seen:
                    continue
                field = DetectedField(schema.field_name, value, schema.sensitivity_weight, "regex", 0.9, _bbox_for_value(value, ocr.words, schema.zone, ocr.image_height))
                field.explanation = explain_field(field, document_type, schema)
                fields.append(field)
                seen.add(key)
                break
        elif schema.field_name == "qr_code" and image_path:
            image = Image.open(image_path).convert("RGB")
            for box in detect_qr_codes(image):
                field = DetectedField("qr_code", "QR_CODE", schema.sensitivity_weight, "image", 0.88, box)
                field.explanation = explain_field(field, document_type, schema)
                fields.append(field)
        elif schema.field_name == "signature":
            anchored = _keyword_anchor_value(schema, ocr.words, ocr.image_height)
            if anchored:
                _, box, _ = anchored
                y = max(box.y, int(ocr.image_height * 0.65))
                sig_box = BoundingBox(max(0, box.x - 20), y, max(160, int(ocr.image_width * 0.35)), max(40, int(ocr.image_height * 0.12)))
                field = DetectedField("signature", "SIGNATURE_REGION", schema.sensitivity_weight, "image", 0.7, sig_box)
                field.explanation = explain_field(field, document_type, schema)
                fields.append(field)
        else:
            fields.extend(_ner_fields(ocr.text, ocr.words, ocr.image_height, schema, document_type))
    return fields


def extract_unknown_fields(ocr: OCRResult) -> list[DetectedField]:
    fields: list[DetectedField] = []
    for name, (pattern, weight, description) in UNIVERSAL_REGEX_PATTERNS.items():
        for match in re.finditer(pattern, ocr.text, re.IGNORECASE if "pattern" not in name else 0):
            field = DetectedField(name, match.group(0), weight, "regex", 0.85, _bbox_for_value(match.group(0), ocr.words, "anywhere", ocr.image_height))
            field.explanation = f"{name} detected because the value '{field.field_value}' matches the universal {description}."
            fields.append(field)
    model = _load_spacy_model()
    if model is not None and getattr(model, "pipe_names", []):
        weights = {"PERSON": 5, "GPE": 5, "LOC": 5, "ORG": 3}
        for entity in model(ocr.text).ents:
            if entity.label_ in weights:
                field = DetectedField(entity.label_.lower(), entity.text, weights[entity.label_], "ner", 0.7, _bbox_for_value(entity.text, ocr.words, "anywhere", ocr.image_height), metadata={"entity_type": entity.label_})
                field.explanation = explain_field(field, "unknown")
                fields.append(field)
    return fields
