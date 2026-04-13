from __future__ import annotations

import json
import sqlite3

from securemask.config import DB_PATH, ensure_storage_dirs
from securemask.models.scan import ScanSession


def get_connection() -> sqlite3.Connection:
    ensure_storage_dirs()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                scan_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                filename TEXT NOT NULL,
                document_type TEXT NOT NULL,
                document_type_confidence REAL NOT NULL,
                declared_context TEXT NOT NULL,
                original_file_path TEXT,
                processable_image_path TEXT,
                raw_text TEXT NOT NULL,
                detected_fields_json TEXT NOT NULL,
                pei_before REAL NOT NULL,
                pei_after REAL,
                redacted_file_path TEXT,
                audit_report_json TEXT,
                highlighted_text TEXT,
                needs_review_count INTEGER DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_value TEXT,
                detection_method TEXT,
                confidence REAL,
                needs_review BOOLEAN DEFAULT 0,
                always_redact BOOLEAN DEFAULT 0,
                required BOOLEAN DEFAULT 0,
                redaction_decision TEXT DEFAULT 'redact',
                sensitivity_weight INTEGER,
                FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scans(scan_id)
            )
            """
        )
        connection.commit()
