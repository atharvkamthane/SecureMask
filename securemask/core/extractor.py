"""Field extraction coordinator.

Routes each field to QR → MRZ → regex_fuzzy → NER based on extraction_method.
Handles all 5 document types with QR/MRZ special paths.
"""
from __future__ import annotations

import logging
import re

import cv2
import numpy as np
from PIL import Image

from securemask.core.fuzzy_regex import FuzzyRegexExtractor
from securemask.core.mrz import MRZParser
from securemask.core.ner import NERExtractor
from securemask.core.ocr import OCRResult
from securemask.core.qr import QRDecoder
from securemask.models.detected_field import BoundingBox, DetectedField
from securemask.schemas import get_schema

logger = logging.getLogger(__name__)

# Singletons
_fuzzy = FuzzyRegexExtractor()
_ner = NERExtractor()
_mrz = MRZParser()
_qr = QRDecoder()


def _normalize_bbox_pct(box: BoundingBox, w: int, h: int) -> BoundingBox:
    if w <= 0 or h <= 0:
        return box
    return BoundingBox(
        x=round(box.x / w * 100, 2),
        y=round(box.y / h * 100, 2),
        width=round(box.width / w * 100, 2),
        height=round(box.height / h * 100, 2),
    )


def _detect_photo_region(image_path: str) -> BoundingBox | None:
    """Detect face region using OpenCV Haar cascade."""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
        if len(faces) > 0:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            pad = int(w * 0.3)
            return BoundingBox(
                max(0, x - pad), max(0, y - pad),
                min(img.shape[1], w + 2 * pad),
                min(img.shape[0], h + 2 * pad),
            )
    except Exception:
        pass
    return None


class FieldExtractor:
    """Coordinate field extraction across QR, MRZ, regex, and NER engines."""

    def extract(self, ocr_result: OCRResult, image: Image.Image,
                document_type: str, image_path: str | None = None) -> list[DetectedField]:
        schema_fields = get_schema(document_type)
        if not schema_fields:
            return self._extract_unknown(ocr_result)

        # Pre-compute special decoders
        qr_data = None
        mrz_data = None

        if document_type == "aadhaar":
            qr_data = _qr.decode(image)
            if qr_data:
                logger.info("Aadhaar QR decoded successfully")

        if document_type == "passport":
            mrz_data = _mrz.parse(image_path=image_path, ocr_text=ocr_result.full_text)
            if mrz_data:
                logger.info("Passport MRZ decoded successfully")

        results: list[DetectedField] = []
        seen: set[str] = set()

        for schema in schema_fields:
            if schema.field_name in seen:
                continue

            detected = self._extract_field(
                schema, ocr_result, image, image_path,
                qr_data, mrz_data,
            )
            if detected:
                results.append(detected)
                seen.add(schema.field_name)

        # Normalize bounding boxes to percentages
        for field in results:
            field.bounding_box_pct = _normalize_bbox_pct(
                field.bounding_box, ocr_result.image_width, ocr_result.image_height
            )

        return results

    def _extract_field(self, schema, ocr_result, image, image_path,
                       qr_data=None, mrz_data=None) -> DetectedField | None:
        value = None
        confidence = 0.0
        method_used = "unknown"
        bbox = BoundingBox(0, 0, 1, 1)

        method = schema.extraction_method

        # 1. QR decode path (Aadhaar)
        if "qr_primary" in method and qr_data:
            value = qr_data.get(schema.field_name)
            if value:
                confidence = 0.98
                method_used = "qr"
                # QR doesn't have per-field bbox — use full text search
                bbox = self._find_bbox_in_words(value, ocr_result.words)

        # 2. MRZ decode path (Passport)
        if not value and "mrz_primary" in method and mrz_data:
            value = mrz_data.get(schema.field_name)
            if value:
                confidence = 0.95
                method_used = "mrz"
                bbox = self._find_bbox_in_words(value, ocr_result.words)

        # 3. Regex + fuzzy path
        if not value and schema.regex_pattern:
            val, conf, box = _fuzzy.extract(
                ocr_result.full_text,
                schema.regex_pattern,
                schema.fuzzy_threshold,
                ocr_result.words,
                schema.anchor_keywords,
            )
            if val:
                value = val
                confidence = conf
                method_used = "regex_fuzzy"
                bbox = box or bbox

        # 4. NER path (names, addresses)
        if not value and "ner" in method:
            val, conf, box = _ner.extract(
                ocr_result.full_text,
                schema.field_name,
                ocr_result.words,
                schema.anchor_keywords,
            )
            if val:
                value = val
                confidence = conf
                method_used = "ner"
                bbox = box or bbox

        # 5. Image detection path (QR regions, signatures, photos)
        if not value and method == "image":
            if schema.field_name == "qr_code":
                qr_boxes = _qr.detect_qr_regions(image)
                if qr_boxes:
                    value = "QR_CODE"
                    confidence = 0.95
                    method_used = "image"
                    bbox = qr_boxes[0]
            elif schema.field_name == "signature":
                # Signature is typically in bottom-right
                h, w = ocr_result.image_height, ocr_result.image_width
                value = "SIGNATURE_REGION"
                confidence = 0.60
                method_used = "image"
                bbox = BoundingBox(int(w * 0.05), int(h * 0.75), int(w * 0.4), int(h * 0.2))
            elif schema.field_name == "photo":
                if image_path:
                    photo_box = _detect_photo_region(image_path)
                    if photo_box:
                        value = "PHOTO_REGION"
                        confidence = 0.85
                        method_used = "image"
                        bbox = photo_box

        if not value:
            return None

        return DetectedField(
            field_name=schema.field_name,
            field_value=value,
            sensitivity_weight=schema.sensitivity_weight,
            detection_method=method_used,
            confidence=confidence,
            bounding_box=bbox,
            always_redact=schema.always_redact,
        )

    def _extract_unknown(self, ocr_result: OCRResult) -> list[DetectedField]:
        """Full NER fallback for unknown documents."""
        from securemask.config import UNIVERSAL_REGEX_PATTERNS
        fields: list[DetectedField] = []
        seen: set[str] = set()

        # Universal regex patterns
        for name, (pattern, weight, desc) in UNIVERSAL_REGEX_PATTERNS.items():
            for match in re.finditer(pattern, ocr_result.full_text, re.IGNORECASE):
                val = match.group()
                if val.lower() in seen:
                    continue
                seen.add(val.lower())
                bbox = self._find_bbox_in_words(val, ocr_result.words)
                fields.append(DetectedField(
                    field_name=name, field_value=val,
                    sensitivity_weight=weight, detection_method="regex_fuzzy",
                    confidence=0.85, bounding_box=bbox,
                ))
                break

        # NER on full text
        for field_name, target_type in [("name", "PER"), ("address", "LOC")]:
            val, conf, bbox = _ner.extract(
                ocr_result.full_text, field_name, ocr_result.words, []
            )
            if val and val.lower() not in seen:
                seen.add(val.lower())
                fields.append(DetectedField(
                    field_name=field_name, field_value=val,
                    sensitivity_weight=5, detection_method="ner",
                    confidence=conf, bounding_box=bbox or BoundingBox(0, 0, 1, 1),
                ))

        return fields

    def _find_bbox_in_words(self, value: str, words) -> BoundingBox:
        value_parts = set(re.findall(r"\w+", value.lower()))
        matched = [w for w in words if re.sub(r"\W+", "", w.text).lower() in value_parts]
        if matched:
            left = min(w.bbox.x for w in matched)
            top = min(w.bbox.y for w in matched)
            right = max(w.bbox.x + w.bbox.width for w in matched)
            bottom = max(w.bbox.y + w.bbox.height for w in matched)
            return BoundingBox(left, top, right - left, bottom - top)
        return BoundingBox(0, 0, 1, 1)
