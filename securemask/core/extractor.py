"""Field extraction coordinator.

Routes each field through: QR → MRZ → regex_fuzzy → NER → image detection.
Handles all 5 document types.

Key fixes vs previous version:
  - _preprocess_ocr_text() normalises common OCR substitutions before extraction
    so that digit-pattern regex matches survive garbled OCR output.
  - Aadhaar number gets a dedicated broad-scan fallback: it scans all 4-4-4
    digit groups in the entire text regardless of zone or anchor proximity.
  - DOB anchor window extended and pattern tries multiple date formats.
  - Low-confidence EasyOCR words are excluded from NER to cut false positives.
"""
from __future__ import annotations

import logging
import re

import cv2
import numpy as np
from PIL import Image

from securemask.core.fuzzy_regex import FuzzyRegexExtractor, _clean_for_digits
from securemask.core.mrz import MRZParser
from securemask.core.ner import NERExtractor
from securemask.core.ocr import OCRResult, OCRWord
from securemask.core.qr import QRDecoder
from securemask.models.detected_field import BoundingBox, DetectedField
from securemask.schemas import get_schema

logger = logging.getLogger(__name__)

_fuzzy = FuzzyRegexExtractor()
_ner   = NERExtractor()
_mrz   = MRZParser()
_qr    = QRDecoder()

# ------------------------------------------------------------------
# OCR text pre-processing
# ------------------------------------------------------------------

# Aadhaar UID: 12 digits in groups of 4, optionally separated by spaces/hyphens
_AADHAAR_RE = re.compile(r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b')

# DOB: many formats OCR'd from Indian IDs
_DOB_RE = re.compile(
    r'\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})'   # DD/MM/YYYY or DD-MM-YY
    r'|\b(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})'     # YYYY/MM/DD
    r'|\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b',           # DD/MM/YYYY strict
)


def _preprocess_ocr_text(ocr_result: OCRResult) -> OCRResult:
    """Return a cleaned copy of the OCR result with common substitutions fixed.

    Does NOT modify word bboxes — the original bboxes are still correct because
    character-level substitutions don't change string length (1-for-1 replacement).
    """
    cleaned_full = _clean_for_digits(ocr_result.full_text)

    cleaned_words = []
    for w in ocr_result.words:
        cleaned_words.append(OCRWord(
            text=_clean_for_digits(w.text),
            confidence=w.confidence,
            bbox=w.bbox,
        ))

    return OCRResult(
        full_text=cleaned_full,
        words=cleaned_words,
        image_width=ocr_result.image_width,
        image_height=ocr_result.image_height,
    )


# ------------------------------------------------------------------
# Bounding box helpers
# ------------------------------------------------------------------

def _normalize_bbox_pct(box: BoundingBox, w: int, h: int) -> BoundingBox:
    if w <= 0 or h <= 0:
        return box
    return BoundingBox(
        x=round(box.x / w * 100, 2),
        y=round(box.y / h * 100, 2),
        width=round(box.width / w * 100, 2),
        height=round(box.height / h * 100, 2),
    )


# ------------------------------------------------------------------
# Visual region detectors
# ------------------------------------------------------------------

def _detect_photo_region(image_path: str) -> BoundingBox | None:
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        img_h, img_w = img.shape[:2]
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1,
                                          minNeighbors=4, minSize=(30, 30))
        candidates = []
        for x, y, w, h in faces:
            area_ratio   = (w * h) / max(1, img_w * img_h)
            width_ratio  = w / max(1, img_w)
            height_ratio = h / max(1, img_h)
            aspect       = w / max(1, h)
            if area_ratio > 0.18 or width_ratio > 0.38 or height_ratio > 0.55:
                continue
            if not 0.55 <= aspect <= 1.45:
                continue
            center_x = x + w / 2
            if 0.35 * img_w < center_x < 0.65 * img_w and area_ratio > 0.04:
                continue
            candidates.append((x, y, w, h, area_ratio))

        if candidates:
            x, y, w, h, _ = max(candidates, key=lambda f: f[4])
            pad_x  = int(w * 0.18)
            pad_y  = int(h * 0.22)
            left   = int(max(0, x - pad_x))
            top    = int(max(0, y - pad_y))
            right  = int(min(img_w, x + w + pad_x))
            bottom = int(min(img_h, y + h + pad_y))
            return BoundingBox(left, top, right - left, bottom - top)
    except Exception:
        pass
    return None


def _detect_signature_region(image_path: str, doc_type: str,
                               img_w: int, img_h: int) -> BoundingBox:
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError('Could not read image')
        roi_y_start = int(img_h * 0.65)
        roi         = img[roi_y_start:, :]
        gray        = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh   = cv2.threshold(gray, 0, 255,
                                     cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        best_box  = None
        best_score = 0.0
        roi_h, roi_w = roi.shape[:2]
        for cnt in contours:
            cx, cy, cw, ch = cv2.boundingRect(cnt)
            aspect     = cw / max(ch, 1)
            area_frac  = (cw * ch) / max(roi_w * roi_h, 1)
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
        logger.debug('Signature detection failed: %s', exc)

    fallbacks = {
        'pan':             BoundingBox(int(img_w*0.05), int(img_h*0.72), int(img_w*0.45), int(img_h*0.15)),
        'driving_license': BoundingBox(int(img_w*0.50), int(img_h*0.70), int(img_w*0.40), int(img_h*0.15)),
    }
    return fallbacks.get(doc_type,
        BoundingBox(int(img_w*0.05), int(img_h*0.75), int(img_w*0.4), int(img_h*0.18)))


# ------------------------------------------------------------------
# Aadhaar-specific broad scan (fallback when schema regex misses)
# ------------------------------------------------------------------

def _aadhaar_number_broad_scan(
    ocr_result: OCRResult,
    cleaned_result: OCRResult,
) -> DetectedField | None:
    """Last-resort scan for the 12-digit Aadhaar UID anywhere in the text.

    The UID appears in large type at the bottom of the card. Proximity-based
    filtering can skip it when 'aadhaar' label is far away in OCR text order.
    We scan both raw and cleaned text and accept the first valid 12-digit group.
    """
    for text, words in [
        (cleaned_result.full_text, cleaned_result.words),
        (ocr_result.full_text,     ocr_result.words),
    ]:
        for m in _AADHAAR_RE.finditer(text):
            uid = re.sub(r'[\s\-]', '', m.group())
            if len(uid) == 12 and uid.isdigit():
                # Skip obviously fake UIDs (all same digit, or all zeros)
                if len(set(uid)) < 3:
                    continue
                raw_val = m.group().strip()
                bbox = _find_bbox_in_words(raw_val, words)
                logger.info("Aadhaar broad-scan found UID: %s****", uid[:4])
                from securemask.models.detected_field import DetectedField
                return DetectedField(
                    field_name='aadhaar_number',
                    field_value=raw_val,
                    sensitivity_weight=10,
                    detection_method='regex_fuzzy',
                    confidence=0.90,
                    bounding_box=bbox,
                    always_redact=False,
                )
    return None


def _dob_broad_scan(
    ocr_result: OCRResult,
    cleaned_result: OCRResult,
) -> DetectedField | None:
    """Fallback DOB scan across the entire text with multiple date formats."""
    from datetime import date
    current_year = date.today().year

    for text, words in [
        (ocr_result.full_text, ocr_result.words),
        (cleaned_result.full_text, cleaned_result.words),
    ]:
        for m in _DOB_RE.finditer(text):
            val = next(g for g in m.groups() if g)
            # Validate year is plausible
            years = re.findall(r'\d{4}', val)
            if years and not any(1900 <= int(y) <= current_year for y in years):
                continue
            # Skip dates that look like ID numbers (no separator variety)
            if re.fullmatch(r'\d+', val):
                continue
            bbox = _find_bbox_in_words(val, words)
            logger.info("DOB broad-scan found: %s", val)
            return DetectedField(
                field_name='dob',
                field_value=val,
                sensitivity_weight=6,
                detection_method='regex_fuzzy',
                confidence=0.82,
                bounding_box=bbox,
                always_redact=False,
            )
    return None


# ------------------------------------------------------------------
# Shared bbox helper
# ------------------------------------------------------------------

def _find_bbox_in_words(value: str, words: list[OCRWord]) -> BoundingBox:
    from securemask.utils.bbox_utils import find_bbox_in_words
    return find_bbox_in_words(value, words)


# ------------------------------------------------------------------
# Main extractor class
# ------------------------------------------------------------------

class FieldExtractor:
    """Coordinate field extraction across QR, MRZ, regex, and NER engines."""

    def extract(
        self,
        ocr_result: OCRResult,
        image: Image.Image,
        document_type: str,
        image_path: str | None = None,
    ) -> list[DetectedField]:
        # Clean OCR text once — used by all sub-extractors
        cleaned_ocr = _preprocess_ocr_text(ocr_result)

        schema_fields = get_schema(document_type)
        if not schema_fields:
            # Unknown type: trial all schemas, pick highest-scoring
            best_results = self._extract_unknown(ocr_result, cleaned_ocr)
            best_score   = sum(f.confidence for f in best_results)

            from securemask.schemas import SUPPORTED_TYPES
            for try_type in SUPPORTED_TYPES:
                try_r = self._extract_for_type(
                    ocr_result, cleaned_ocr, image, try_type, image_path
                )
                high = [f for f in try_r if f.confidence > 0.7]
                score = len(high) * 1.0 + sum(f.confidence for f in high)
                if score > best_score and try_r:
                    best_score   = score
                    best_results = try_r
                    logger.info("Unknown doc: schema '%s' → %d fields (score=%.2f)",
                                try_type, len(try_r), score)
            return best_results

        return self._extract_for_type(
            ocr_result, cleaned_ocr, image, document_type, image_path
        )

    # ------------------------------------------------------------------
    # Per-type extraction pipeline
    # ------------------------------------------------------------------

    def _extract_for_type(
        self,
        ocr_result: OCRResult,
        cleaned_ocr: OCRResult,
        image: Image.Image,
        document_type: str,
        image_path: str | None,
    ) -> list[DetectedField]:
        schema_fields = get_schema(document_type)
        if not schema_fields:
            return []

        # Special decoders
        qr_data  = None
        mrz_data = None

        if document_type == 'aadhaar':
            qr_data = _qr.decode(image)
            if qr_data:
                logger.info('Aadhaar QR decoded successfully')

        if document_type == 'passport':
            mrz_data = _mrz.parse(image_path=image_path,
                                   ocr_text=ocr_result.full_text)
            if mrz_data:
                logger.info('Passport MRZ decoded successfully')

        results: list[DetectedField] = []
        seen: set[str] = set()

        for schema in schema_fields:
            if schema.field_name in seen:
                continue

            # Zone-filtered slice of OCR result
            zone_ocr         = self._filter_ocr_by_zone(ocr_result, schema.zone)
            zone_ocr_cleaned = self._filter_ocr_by_zone(cleaned_ocr, schema.zone)

            # Try with zone filter first
            detected = self._extract_field(
                schema, zone_ocr, zone_ocr_cleaned,
                image, image_path, qr_data, mrz_data, document_type,
            )

            # Fallback: full text if zone-filtered attempt failed
            if not detected and schema.zone not in ('anywhere', None):
                detected = self._extract_field(
                    schema, ocr_result, cleaned_ocr,
                    image, image_path, qr_data, mrz_data, document_type,
                )

            if detected:
                results.append(detected)
                seen.add(schema.field_name)

        # ---- Broad-scan fallbacks for Aadhaar ----
        if document_type == 'aadhaar':
            if 'aadhaar_number' not in seen and not qr_data:
                found = _aadhaar_number_broad_scan(ocr_result, cleaned_ocr)
                if found:
                    results.append(found)
                    seen.add('aadhaar_number')
                    logger.info('Aadhaar number recovered via broad-scan')

            if 'dob' not in seen:
                found = _dob_broad_scan(ocr_result, cleaned_ocr)
                if found:
                    results.append(found)
                    seen.add('dob')
                    logger.info('DOB recovered via broad-scan')

        # Collision: remove father_name if identical to name (NER confusion)
        name_field = next((r for r in results if r.field_name == 'name'), None)
        if name_field:
            from rapidfuzz import fuzz
            results = [
                r for r in results
                if r.field_name not in ('father_name', 'father_husband_name', 'father_spouse_name')
                   or fuzz.ratio(r.field_value.strip().lower(),
                                  name_field.field_value.strip().lower()) <= 90
            ]

        # Normalise bounding boxes to percentages
        for field in results:
            field.bounding_box_pct = _normalize_bbox_pct(
                field.bounding_box,
                ocr_result.image_width,
                ocr_result.image_height,
            )

        return results

    # ------------------------------------------------------------------
    # Single-field extraction
    # ------------------------------------------------------------------

    def _extract_field(
        self,
        schema,
        ocr_result: OCRResult,
        cleaned_ocr: OCRResult,
        image: Image.Image,
        image_path: str | None,
        qr_data,
        mrz_data,
        document_type: str,
    ) -> DetectedField | None:
        value      = None
        confidence = 0.0
        method     = schema.extraction_method
        bbox       = BoundingBox(0, 0, 1, 1)
        method_used = 'unknown'

        # 1. QR (Aadhaar)
        if 'qr_primary' in method and qr_data:
            value = qr_data.get(schema.field_name)
            if value:
                confidence  = 0.98
                method_used = 'qr'
                bbox        = _find_bbox_in_words(value, ocr_result.words)

        # 2. MRZ (Passport)
        if not value and 'mrz_primary' in method and mrz_data:
            value = mrz_data.get(schema.field_name)
            if value:
                confidence  = 0.95
                method_used = 'mrz'
                bbox        = _find_bbox_in_words(value, ocr_result.words)

        # 3. Regex + fuzzy (try cleaned text first, fall back to raw)
        if not value and schema.regex_pattern:
            for src_ocr in (cleaned_ocr, ocr_result):
                val, conf, box = _fuzzy.extract(
                    src_ocr.full_text,
                    schema.regex_pattern,
                    schema.fuzzy_threshold,
                    src_ocr.words,
                    schema.anchor_keywords,
                )
                if val:
                    value       = val
                    confidence  = conf
                    method_used = 'regex_fuzzy'
                    bbox        = box or bbox
                    break

        # 4. NER (names, addresses)
        if not value and 'ner' in method:
            val, conf, box = _ner.extract(
                ocr_result.full_text,
                schema.field_name,
                ocr_result.words,
                schema.anchor_keywords,
            )
            if val:
                value       = val
                confidence  = conf
                method_used = 'ner'
                bbox        = box or bbox

        # 5. Image detection (QR region, signature, photo)
        if not value and method == 'image':
            if schema.field_name == 'qr_code':
                qr_boxes = _qr.detect_qr_regions(image)
                if qr_boxes:
                    value       = 'QR_CODE'
                    confidence  = 0.95
                    method_used = 'image'
                    bbox        = qr_boxes[0]

            elif schema.field_name == 'signature':
                h = ocr_result.image_height
                w = ocr_result.image_width
                sig_box     = (_detect_signature_region(image_path, document_type, w, h)
                               if image_path else
                               BoundingBox(int(w*0.05), int(h*0.75), int(w*0.4), int(h*0.18)))
                value       = 'SIGNATURE_REGION'
                confidence  = 0.65
                method_used = 'image'
                bbox        = sig_box

            elif schema.field_name == 'photo':
                if image_path:
                    photo_box = _detect_photo_region(image_path)
                    if photo_box:
                        value       = 'PHOTO_REGION'
                        confidence  = 0.85
                        method_used = 'image'
                        bbox        = photo_box

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

    # ------------------------------------------------------------------
    # Unknown-document fallback
    # ------------------------------------------------------------------

    def _extract_unknown(
        self,
        ocr_result: OCRResult,
        cleaned_ocr: OCRResult,
    ) -> list[DetectedField]:
        from securemask.config import UNIVERSAL_REGEX_PATTERNS
        fields: list[DetectedField] = []
        seen: set[str] = set()

        for name, (pattern, weight, _desc) in UNIVERSAL_REGEX_PATTERNS.items():
            for text in (cleaned_ocr.full_text, ocr_result.full_text):
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    val = m.group()
                    if val.lower() in seen:
                        continue
                    seen.add(val.lower())
                    bbox = _find_bbox_in_words(val, ocr_result.words)
                    fields.append(DetectedField(
                        field_name=name, field_value=val,
                        sensitivity_weight=weight,
                        detection_method='regex_fuzzy',
                        confidence=0.85, bounding_box=bbox,
                    ))
                    break
                if name in seen:
                    break

        for field_name in ('name', 'address'):
            val, conf, bbox = _ner.extract(
                ocr_result.full_text, field_name, ocr_result.words, []
            )
            if val and val.lower() not in seen:
                seen.add(val.lower())
                fields.append(DetectedField(
                    field_name=field_name, field_value=val,
                    sensitivity_weight=5, detection_method='ner',
                    confidence=conf, bounding_box=bbox or BoundingBox(0, 0, 1, 1),
                ))

        return fields

    # ------------------------------------------------------------------
    # OCR zone filtering
    # ------------------------------------------------------------------

    def _filter_ocr_by_zone(
        self, ocr_result: OCRResult, zone: str | None
    ) -> OCRResult:
        if not zone or zone not in ('top', 'middle', 'bottom') or ocr_result.image_height <= 0:
            return ocr_result

        h = ocr_result.image_height
        filtered = []
        for w in ocr_result.words:
            y_ratio = (w.bbox.y + w.bbox.height / 2) / h
            if zone == 'top'    and y_ratio <  0.45: filtered.append(w)
            if zone == 'middle' and 0.20 <= y_ratio < 0.80: filtered.append(w)
            if zone == 'bottom' and y_ratio >= 0.50: filtered.append(w)

        filtered.sort(key=lambda word: (word.bbox.y, word.bbox.x))
        return OCRResult(
            full_text=' '.join(w.text for w in filtered),
            words=filtered,
            image_width=ocr_result.image_width,
            image_height=ocr_result.image_height,
        )
    
    