"""SecureMask API routes — Pydantic response models + full pipeline endpoints."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from pydantic import BaseModel

from securemask.config import (
    PROCESSED_DIR, REDACTED_DIR, SUPPORTED_CONTEXTS, UPLOAD_DIR, ensure_storage_dirs,
)
from securemask.core.audit import generate_audit_report
from securemask.core.classifier import DocumentClassifier
from securemask.core.explainer import generate_explanation
from securemask.core.extractor import FieldExtractor
from securemask.core.necessity import check_necessity
from securemask.core.ocr import OCREngine
from securemask.core.pei import compute_pei, compute_pei_after_redaction
from securemask.core.preprocessor import preprocess
from securemask.core.redactor import redact_image
from securemask.db.database import get_connection
from securemask.models.detected_field import BoundingBox, DetectedField

logger = logging.getLogger(__name__)
router = APIRouter()

# Singletons (lazy-init on first request)
_ocr_engine: OCREngine | None = None
_classifier: DocumentClassifier | None = None
_extractor: FieldExtractor | None = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine()
    return _ocr_engine


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = DocumentClassifier()
    return _classifier


def _get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = FieldExtractor()
    return _extractor


# ───────────────────────────────── Pydantic Models ─────────────────────────────

class BBoxResponse(BaseModel):
    x: float
    y: float
    width: float
    height: float


class FieldResponse(BaseModel):
    field_name: str
    field_value: str
    sensitivity_weight: int
    detection_method: str
    confidence: float
    bounding_box: BBoxResponse
    bounding_box_pct: BBoxResponse | None = None
    needs_review: bool
    always_redact: bool
    explanation: str
    required: bool
    redaction_decision: str


class UploadResponse(BaseModel):
    scan_id: str
    document_type: str
    confidence: float
    declared_context: str
    detected_fields: list[FieldResponse]
    pei_before: float
    needs_review_count: int
    raw_text: str
    original_file_url: str
    processable_image_url: str


class RedactRequest(BaseModel):
    scan_id: str
    decisions: dict[str, str]


class RedactResponse(BaseModel):
    pei_after: float
    redacted_image_url: str
    audit_report: dict[str, Any]


class AuditResponse(BaseModel):
    scan_id: str
    timestamp: str
    filename: str
    document_type: str
    document_type_confidence: float
    declared_context: str
    pei_before: float
    pei_after: float
    fields_detected: list[dict[str, Any]]
    compliance_notes: dict[str, str]
    redacted_file_path: str


class ScanSummary(BaseModel):
    scan_id: str
    timestamp: str
    filename: str
    document_type: str
    declared_context: str
    pei_before: float
    pei_after: float | None
    needs_review_count: int


class ScanTextRequest(BaseModel):
    text: str
    context: str


class ScanTextResponse(BaseModel):
    detected_fields: list[FieldResponse]
    pei_before: float
    highlighted_text: str


# ─────────────────────────────── POST /upload ──────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...),
                          context: str = Form("general_upload")):
    """Full pipeline: preprocess → OCR → classify → extract → necessity → PEI → explain."""
    ensure_storage_dirs()

    if context not in SUPPORTED_CONTEXTS:
        raise HTTPException(400, f"Invalid context. Must be one of: {SUPPORTED_CONTEXTS}")

    scan_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Save uploaded file
    upload_dir = UPLOAD_DIR / scan_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_path = upload_dir / file.filename
    content = await file.read()
    original_path.write_bytes(content)

    # Preprocess
    proc_dir = PROCESSED_DIR / scan_id
    proc_dir.mkdir(parents=True, exist_ok=True)
    processable_path = proc_dir / "preprocessed.png"

    try:
        binary, color, pil_color = preprocess(original_path)
        import cv2
        cv2.imwrite(str(processable_path), binary)
    except Exception as exc:
        logger.error("Preprocessing failed: %s", exc)
        # Use original as fallback
        from PIL import Image
        pil_color = Image.open(original_path).convert("RGB")
        pil_color.save(processable_path, "PNG")

    # OCR
    ocr_engine = _get_ocr()
    ocr_result = ocr_engine.extract(str(original_path))

    # Classify
    classifier = _get_classifier()
    classification = classifier.classify_with_text_fallback(pil_color, ocr_result.full_text)

    # Extract fields
    extractor = _get_extractor()
    detected_fields = extractor.extract(ocr_result, pil_color, classification.document_type, str(original_path))

    # Necessity check
    necessity_results: dict[str, bool] = {}
    for field in detected_fields:
        required = check_necessity(classification.document_type, field.field_name, context)
        field.required = required
        necessity_results[field.field_name] = required
        # Default decision: redact excess fields, allow required ones
        if field.always_redact:
            field.redaction_decision = "redact"
        elif required:
            field.redaction_decision = "allow"
        else:
            field.redaction_decision = "redact"

    # PEI
    pei_before = compute_pei(detected_fields, necessity_results)

    # Explanations
    for field in detected_fields:
        field.explanation = generate_explanation(field, classification.document_type)

    needs_review_count = sum(1 for f in detected_fields if f.needs_review)

    # Save to DB
    _save_scan(scan_id, timestamp, file.filename, classification.document_type,
               classification.confidence, context, str(original_path),
               str(processable_path), ocr_result.full_text, detected_fields,
               pei_before, needs_review_count)

    # Build response
    return UploadResponse(
        scan_id=scan_id,
        document_type=classification.document_type,
        confidence=round(classification.confidence, 3),
        declared_context=context,
        detected_fields=[_field_to_response(f) for f in detected_fields],
        pei_before=pei_before,
        needs_review_count=needs_review_count,
        raw_text=ocr_result.full_text,
        original_file_url=f"/files/uploads/{scan_id}/{file.filename}",
        processable_image_url=f"/files/processed/{scan_id}/preprocessed.png",
    )


# ─────────────────────────────── POST /redact ──────────────────────────────────

@router.post("/redact", response_model=RedactResponse)
async def redact_document(request: RedactRequest):
    """Apply redaction and compute post-redaction PEI."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (request.scan_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Scan not found")

    # Reconstruct fields
    fields_data = json.loads(row["detected_fields_json"])
    fields = [DetectedField.from_dict(f) for f in fields_data]

    # Apply decisions
    for field in fields:
        decision = request.decisions.get(field.field_name, "allow")
        if field.always_redact:
            decision = "redact"
        field.redaction_decision = decision

    # Necessity results
    context = row["declared_context"]
    doc_type = row["document_type"]
    necessity_results = {f.field_name: check_necessity(doc_type, f.field_name, context) for f in fields}

    # PEI after
    pei_after = compute_pei_after_redaction(fields, necessity_results, request.decisions)

    # Redact image
    redact_dir = REDACTED_DIR / request.scan_id
    redact_dir.mkdir(parents=True, exist_ok=True)
    redacted_path = redact_dir / "redacted.png"
    original_path = row["original_file_path"]

    redact_image(original_path, fields, redacted_path, request.decisions)

    # Generate audit report
    audit = generate_audit_report(
        request.scan_id, row["timestamp"], row["filename"],
        doc_type, row["document_type_confidence"],
        context, row["pei_before"], pei_after, fields,
        str(redacted_path),
    )

    # Update DB
    conn.execute(
        "UPDATE scans SET pei_after = ?, redacted_file_path = ?, audit_report_json = ?, detected_fields_json = ? WHERE scan_id = ?",
        (pei_after, str(redacted_path), json.dumps(audit.to_dict()),
         json.dumps([f.to_dict() for f in fields]), request.scan_id),
    )
    conn.commit()

    return RedactResponse(
        pei_after=pei_after,
        redacted_image_url=f"/files/redacted/{request.scan_id}/redacted.png",
        audit_report=audit.to_dict(),
    )


# ─────────────────────────────── GET /audit/{scan_id} ──────────────────────────

@router.get("/audit/{scan_id}")
async def get_audit(scan_id: str):
    conn = get_connection()
    row = conn.execute("SELECT audit_report_json FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Scan not found")
    if not row["audit_report_json"]:
        raise HTTPException(404, "Audit report not yet generated. Run /redact first.")
    return json.loads(row["audit_report_json"])


# ─────────────────────────────── GET /scans ────────────────────────────────────

@router.get("/scans", response_model=list[ScanSummary])
async def list_scans():
    conn = get_connection()
    rows = conn.execute(
        "SELECT scan_id, timestamp, filename, document_type, declared_context, "
        "pei_before, pei_after, needs_review_count FROM scans ORDER BY timestamp DESC"
    ).fetchall()
    return [ScanSummary(**dict(r)) for r in rows]


# ─────────────────────────────── POST /scan-text ───────────────────────────────

@router.post("/scan-text", response_model=ScanTextResponse)
async def scan_text(request: ScanTextRequest):
    """Detect PII in raw text (no image processing)."""
    from securemask.core.ocr import OCRResult, OCRWord
    from securemask.models.detected_field import BoundingBox

    if request.context not in SUPPORTED_CONTEXTS:
        raise HTTPException(400, f"Invalid context")

    # Create mock OCR result from text
    words = [OCRWord(text=w, confidence=1.0, bbox=BoundingBox(0, 0, 1, 1))
             for w in request.text.split()]
    ocr_result = OCRResult(full_text=request.text, words=words, image_width=100, image_height=100)

    # Run field extraction as "unknown" doc type
    extractor = _get_extractor()
    fields = extractor._extract_unknown(ocr_result)

    necessity_results = {}
    for f in fields:
        f.required = False
        necessity_results[f.field_name] = False

    pei = compute_pei(fields, necessity_results)

    # Highlight PII in text
    highlighted = request.text
    for f in fields:
        highlighted = highlighted.replace(f.field_value, f"[{f.field_name}:{f.field_value}]")

    return ScanTextResponse(
        detected_fields=[_field_to_response(f) for f in fields],
        pei_before=pei,
        highlighted_text=highlighted,
    )


# ─────────────────────────────── Helpers ───────────────────────────────────────

def _field_to_response(f: DetectedField) -> FieldResponse:
    bbox = f.bounding_box if f.bounding_box else BoundingBox(0, 0, 1, 1)
    pct = f.bounding_box_pct
    return FieldResponse(
        field_name=f.field_name,
        field_value=f.field_value,
        sensitivity_weight=f.sensitivity_weight,
        detection_method=f.detection_method,
        confidence=round(f.confidence, 3),
        bounding_box=BBoxResponse(x=bbox.x, y=bbox.y, width=bbox.width, height=bbox.height),
        bounding_box_pct=BBoxResponse(x=pct.x, y=pct.y, width=pct.width, height=pct.height) if pct else None,
        needs_review=f.needs_review,
        always_redact=f.always_redact,
        explanation=f.explanation,
        required=f.required,
        redaction_decision=f.redaction_decision,
    )


def _save_scan(scan_id, timestamp, filename, doc_type, doc_conf, context,
               orig_path, proc_path, raw_text, fields, pei_before, review_count):
    conn = get_connection()
    conn.execute(
        """INSERT INTO scans (scan_id, timestamp, filename, document_type,
           document_type_confidence, declared_context, original_file_path,
           processable_image_path, raw_text, detected_fields_json,
           pei_before, needs_review_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (scan_id, timestamp, filename, doc_type, doc_conf, context,
         orig_path, proc_path, raw_text,
         json.dumps([f.to_dict() for f in fields]),
         pei_before, review_count),
    )
    conn.commit()
