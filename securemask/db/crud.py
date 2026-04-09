from __future__ import annotations

import json

from securemask.db.database import get_connection
from securemask.models.scan import ScanSession


def save_scan(scan: ScanSession) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO scans (
                scan_id, timestamp, filename, document_type, document_type_confidence,
                declared_context, original_file_path, processable_image_path, raw_text,
                detected_fields_json, pei_before, pei_after, redacted_file_path,
                audit_report_json, highlighted_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan.scan_id,
                scan.timestamp,
                scan.filename,
                scan.document_type,
                scan.document_type_confidence,
                scan.declared_context,
                scan.original_file_path,
                scan.processable_image_path,
                scan.raw_text,
                json.dumps(scan.detected_fields),
                scan.pei_before,
                scan.pei_after,
                scan.redacted_file_path,
                json.dumps(scan.audit_report) if scan.audit_report else None,
                scan.highlighted_text,
            ),
        )
        connection.commit()


def get_scan(scan_id: str) -> ScanSession | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
    if not row:
        return None
    return ScanSession(
        scan_id=row["scan_id"],
        timestamp=row["timestamp"],
        filename=row["filename"],
        document_type=row["document_type"],
        document_type_confidence=row["document_type_confidence"],
        declared_context=row["declared_context"],
        original_file_path=row["original_file_path"],
        processable_image_path=row["processable_image_path"],
        raw_text=row["raw_text"],
        detected_fields=json.loads(row["detected_fields_json"]),
        pei_before=row["pei_before"],
        pei_after=row["pei_after"],
        redacted_file_path=row["redacted_file_path"],
        audit_report=json.loads(row["audit_report_json"]) if row["audit_report_json"] else None,
        highlighted_text=row["highlighted_text"],
    )


def list_scans() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT scan_id, filename, pei_before, pei_after, timestamp, document_type
            FROM scans
            ORDER BY timestamp DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]
