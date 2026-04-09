from __future__ import annotations

import sqlite3

from securemask.config import DB_PATH, ensure_storage_dirs


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
                highlighted_text TEXT
            )
            """
        )
        connection.commit()
