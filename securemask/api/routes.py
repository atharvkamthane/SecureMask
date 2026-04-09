from __future__ import annotations

import html
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from securemask.config import PROCESSED_DIR, REDACTED_DIR, SUPPORTED_CONTEXTS, UPLOAD_DIR, ensure_storage_dirs
from securemask.core.audit import build_audit_report
from securemask.core.classifier import classify_document
from securemask.core.extractor import extract_fields
from securemask.core.necessity import apply_necessity
from securemask.core.ocr import OCRResult, OCRWord, extract_text_and_boxes
from securemask.core.pei import compute_pei
from securemask.core.redactor import redact_image
from securemask.db import crud
from securemask.models.detected_field import BoundingBox, DetectedField
from securemask.models.scan import ScanSession
from securemask.utils.image_utils import ensure_processable_image

router = APIRouter()


class RedactRequest(BaseModel):
    scan_id: str
    redaction_decisions: dict[str, str]


class ScanTextRequest(BaseModel):
    text: str
    context: str = "general_upload"


def _valid_context(context: str) -> str:
    return context if context in SUPPORTED_CONTEXTS else "general_upload"


def _fields_payload(fields: list[DetectedField]) -> list[dict]:
    return [field.to_dict() for field in fields]


def _fake_ocr_from_text(text: str) -> OCRResult:
    words = []
    x = 20
    y = 20
    for token in text.split():
        width = max(35, len(token) * 8)
        if x + width > 900:
            x = 20
            y += 28
        words.append(OCRWord(token, BoundingBox(x, y, width, 20), 0.8))
        x += width + 8
    return OCRResult(text=text, words=words, image_width=1000, image_height=max(300, y + 60))


def _highlight_text(text: str, fields: list[DetectedField]) -> str:
    highlighted = html.escape(text)
    values = sorted({field.field_value for field in fields if field.field_value and len(field.field_value) > 1}, key=len, reverse=True)
    for value in values:
        escaped = html.escape(value)
        highlighted = re.sub(re.escape(escaped), f"<mark>{escaped}</mark>", highlighted, flags=re.IGNORECASE)
    return highlighted


def _run_scan(scan_id: str, filename: str, text: str, context: str, image_path: str | None, ocr: OCRResult) -> ScanSession:
    document_type, confidence, _ = classify_document(text)
    if confidence < 0.5:
        document_type = "unknown"
    fields = extract_fields(document_type, ocr, image_path=image_path)
    apply_necessity(document_type, context, fields)
    pei_before = compute_pei(fields)
    timestamp = datetime.now(timezone.utc).isoformat()
    return ScanSession(
        scan_id=scan_id,
        timestamp=timestamp,
        filename=filename,
        document_type=document_type,
        document_type_confidence=confidence,
        declared_context=context,
        original_file_path=None,
        processable_image_path=image_path,
        raw_text=text,
        detected_fields=_fields_payload(fields),
        pei_before=pei_before,
        highlighted_text=_highlight_text(text, fields) if image_path is None else None,
    )


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), context: str = Form("general_upload")):
    ensure_storage_dirs()
    context = _valid_context(context)
    scan_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload").suffix or ".png"
    original_path = UPLOAD_DIR / f"{scan_id}{suffix}"
    image_path = PROCESSED_DIR / f"{scan_id}.png"
    with original_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        ensure_processable_image(original_path, image_path)
        ocr = extract_text_and_boxes(image_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Unable to process uploaded document: {exc}") from exc
    scan = _run_scan(scan_id, file.filename or original_path.name, ocr.text, context, str(image_path), ocr)
    scan.original_file_path = str(original_path)
    crud.save_scan(scan)
    return {
        "scan_id": scan.scan_id,
        "document_type": scan.document_type,
        "confidence": scan.document_type_confidence,
        "detected_fields": scan.detected_fields,
        "pei_before": scan.pei_before,
    }


@router.post("/redact")
async def redact_document(payload: RedactRequest):
    scan = crud.get_scan(payload.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not scan.processable_image_path:
        raise HTTPException(status_code=400, detail="This scan has no source image for redaction")
    fields = [DetectedField.from_dict(field) for field in scan.detected_fields]
    for field in fields:
        decision = payload.redaction_decisions.get(field.field_name, field.redaction_decision)
        if decision not in {"redact", "mask", "allow"}:
            raise HTTPException(status_code=422, detail=f"Invalid redaction decision for {field.field_name}")
        field.redaction_decision = decision
    pei_after = compute_pei(fields, after_redaction=True)
    redacted_path = REDACTED_DIR / f"{scan.scan_id}.png"
    redact_image(scan.processable_image_path, fields, redacted_path)
    audit = build_audit_report(
        scan.scan_id,
        scan.timestamp,
        scan.filename,
        scan.document_type,
        scan.document_type_confidence,
        scan.declared_context,
        scan.pei_before,
        pei_after,
        fields,
        str(redacted_path),
    ).to_dict()
    scan.detected_fields = _fields_payload(fields)
    scan.pei_after = pei_after
    scan.redacted_file_path = str(redacted_path)
    scan.audit_report = audit
    crud.save_scan(scan)
    return {
        "pei_after": pei_after,
        "redacted_image_url": f"/files/redacted/{scan.scan_id}.png",
        "audit_report": audit,
    }


@router.get("/audit/{scan_id}")
async def get_audit(scan_id: str):
    scan = crud.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.audit_report:
        return scan.audit_report
    return build_audit_report(
        scan.scan_id,
        scan.timestamp,
        scan.filename,
        scan.document_type,
        scan.document_type_confidence,
        scan.declared_context,
        scan.pei_before,
        scan.pei_after or scan.pei_before,
        [DetectedField.from_dict(field) for field in scan.detected_fields],
        scan.redacted_file_path or "",
    ).to_dict()


@router.get("/scans")
async def scans():
    return crud.list_scans()


@router.post("/scan-text")
async def scan_text(payload: ScanTextRequest):
    context = _valid_context(payload.context)
    scan_id = str(uuid.uuid4())
    ocr = _fake_ocr_from_text(payload.text)
    scan = _run_scan(scan_id, "raw-text", payload.text, context, None, ocr)
    crud.save_scan(scan)
    return {
        "scan_id": scan.scan_id,
        "document_type": scan.document_type,
        "confidence": scan.document_type_confidence,
        "detected_fields": scan.detected_fields,
        "pei_before": scan.pei_before,
        "highlighted_text": scan.highlighted_text,
    }
