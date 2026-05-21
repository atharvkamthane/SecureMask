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
from securemask.core.ocr import OCRResult, OCRWord
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
    """Detect a document portrait while avoiding oversized false positives."""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        img_h, img_w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))

        candidates = []
        for x, y, w, h in faces:
            area_ratio = (w * h) / max(1, img_w * img_h)
            width_ratio = w / max(1, img_w)
            height_ratio = h / max(1, img_h)
            aspect_ratio = w / max(1, h)

            if area_ratio > 0.18 or width_ratio > 0.38 or height_ratio > 0.55:
                continue
            if not 0.55 <= aspect_ratio <= 1.45:
                continue

            # ID portraits are normally near the left/right edge, not covering
            # the center text block. This rejects text clusters mistaken as faces.
            center_x = x + w / 2
            if 0.35 * img_w < center_x < 0.65 * img_w and area_ratio > 0.04:
                continue

            candidates.append((x, y, w, h, area_ratio))

        if candidates:
            x, y, w, h, _ = max(candidates, key=lambda f: f[4])
            pad_x = int(w * 0.18)
            pad_y = int(h * 0.22)
            left = int(max(0, x - pad_x))
            top = int(max(0, y - pad_y))
            right = int(min(img_w, x + w + pad_x))
            bottom = int(min(img_h, y + h + pad_y))
            return BoundingBox(left, top, right - left, bottom - top)
    except Exception:
        pass
    return None


def _detect_signature_region(image_path: str, doc_type: str,
                              img_w: int, img_h: int) -> BoundingBox:
    """Detect signature region using contour analysis in the bottom portion of the image."""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError("Could not read image")

        # Restrict search to bottom 35% of image
        roi_y_start = int(img_h * 0.65)
        roi = img[roi_y_start:, :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Invert and threshold to find dark ink on light background
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Morphological dilation to connect nearby strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Look for a compact horizontal blob that could be a signature
        best_box = None
        best_score = 0.0
        roi_h, roi_w = roi.shape[:2]

        for cnt in contours:
            cx, cy, cw, ch = cv2.boundingRect(cnt)
            # Signature heuristics: wide, not too tall, not full width
            aspect = cw / max(ch, 1)
            area_frac = (cw * ch) / max(roi_w * roi_h, 1)
            if cw < roi_w * 0.05 or cw > roi_w * 0.7:
                continue
            if ch > img_h * 0.20:
                continue
            if not 1.5 <= aspect <= 12:
                continue
            score = area_frac * aspect
            if score > best_score:
                best_score = score
                best_box = (cx, roi_y_start + cy, cw, ch)

        if best_box:
            cx, cy, cw, ch = best_box
            pad = 5
            return BoundingBox(
                int(max(0, cx - pad)), int(max(0, cy - pad)),
                int(min(img_w, cw + pad * 2)), int(min(img_h, ch + pad * 2)),
            )

    except Exception as exc:
        logger.debug("Signature contour detection failed: %s", exc)

    # Per-document-type fallback positions
    fallbacks = {
        "pan": BoundingBox(int(img_w * 0.05), int(img_h * 0.72), int(img_w * 0.45), int(img_h * 0.15)),
        "driving_license": BoundingBox(int(img_w * 0.50), int(img_h * 0.70), int(img_w * 0.40), int(img_h * 0.15)),
    }
    return fallbacks.get(doc_type,
                         BoundingBox(int(img_w * 0.05), int(img_h * 0.75), int(img_w * 0.4), int(img_h * 0.18)))


class FieldExtractor:
    """Coordinate field extraction across QR, MRZ, regex, and NER engines."""

    def extract(self, ocr_result: OCRResult, image: Image.Image,
                document_type: str, image_path: str | None = None) -> list[DetectedField]:
        schema_fields = get_schema(document_type)
        if not schema_fields:
            # Try all known schemas and return whichever yields the most confident fields
            best_results = self._extract_unknown(ocr_result)
            best_score = sum(f.confidence for f in best_results)

            from securemask.schemas import SUPPORTED_TYPES
            for try_type in SUPPORTED_TYPES:
                try_results = self._extract_for_type(ocr_result, image, try_type, image_path)
                high_conf = [f for f in try_results if f.confidence > 0.7]
                score = len(high_conf) * 1.0 + sum(f.confidence for f in high_conf)
                if score > best_score and len(try_results) > 0:
                    best_score = score
                    best_results = try_results
                    logger.info("Unknown doc: schema trial '%s' yielded %d fields (score=%.2f)",
                                try_type, len(try_results), score)

            return best_results

        return self._extract_for_type(ocr_result, image, document_type, image_path)

    def _extract_for_type(self, ocr_result: OCRResult, image: Image.Image,
                          document_type: str, image_path: str | None = None) -> list[DetectedField]:
        schema_fields = get_schema(document_type)
        if not schema_fields:
            return []

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

            # Apply zone-based filtering to OCR result
            zone_ocr = self._filter_ocr_by_zone(ocr_result, schema.zone)

            detected = self._extract_field(
                schema, zone_ocr, image, image_path,
                qr_data, mrz_data, document_type,
            )

            # Fallback if no value detected and zone was constrained
            if not detected and schema.zone not in ("anywhere", None):
                detected = self._extract_field(
                    schema, ocr_result, image, image_path,
                    qr_data, mrz_data, document_type,
                )

            if detected:
                results.append(detected)
                seen.add(schema.field_name)

        # Collision resolution: remove father_name/spouse_name if they are identical to name
        name_field = next((r for r in results if r.field_name == "name"), None)
        if name_field:
            from rapidfuzz import fuzz
            filtered_results = []
            for r in results:
                if r.field_name in ("father_name", "father_husband_name", "father_spouse_name"):
                    ratio = fuzz.ratio(r.field_value.strip().lower(), name_field.field_value.strip().lower())
                    if ratio > 90:
                        logger.info(f"Removing duplicate/collision field {r.field_name} (identical to name: '{r.field_value}')")
                        continue
                filtered_results.append(r)
            results = filtered_results

        # Normalize bounding boxes to percentages
        for field in results:
            field.bounding_box_pct = _normalize_bbox_pct(
                field.bounding_box, ocr_result.image_width, ocr_result.image_height
            )

        return results

    def _extract_field(self, schema, ocr_result, image, image_path,
                       qr_data=None, mrz_data=None, document_type="unknown") -> DetectedField | None:
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
                h, w = ocr_result.image_height, ocr_result.image_width
                if image_path:
                    sig_box = _detect_signature_region(image_path, document_type, w, h)
                else:
                    sig_box = BoundingBox(int(w * 0.05), int(h * 0.75), int(w * 0.4), int(h * 0.18))
                value = "SIGNATURE_REGION"
                confidence = 0.65
                method_used = "image"
                bbox = sig_box
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

    def _filter_ocr_by_zone(self, ocr_result: OCRResult, zone: str | None) -> OCRResult:
        if not zone or zone not in ("top", "middle", "bottom") or ocr_result.image_height <= 0:
            return ocr_result

        h = ocr_result.image_height
        filtered_words = []
        for w in ocr_result.words:
            # Calculate vertical center of the word bounding box
            y_center = w.bbox.y + w.bbox.height / 2
            y_ratio = y_center / h

            if zone == "top" and y_ratio < 0.45:
                filtered_words.append(w)
            elif zone == "middle" and 0.20 <= y_ratio < 0.80:
                filtered_words.append(w)
            elif zone == "bottom" and y_ratio >= 0.50:
                filtered_words.append(w)

        filtered_words.sort(key=lambda word: (word.bbox.y, word.bbox.x))
        filtered_text = " ".join(w.text for w in filtered_words)

        return OCRResult(
            full_text=filtered_text,
            words=filtered_words,
            image_width=ocr_result.image_width,
            image_height=ocr_result.image_height,
        )

    def _find_bbox_in_words(self, value: str, words: list[OCRWord]) -> BoundingBox:
        from securemask.utils.bbox_utils import find_bbox_in_words
        return find_bbox_in_words(value, words)
