"""SecureMask FastAPI application entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from securemask.api.routes import router
from securemask.config import PROCESSED_DIR, REDACTED_DIR, UPLOAD_DIR, ensure_storage_dirs
from securemask.db.database import init_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="SecureMask API",
    description="Document privacy protection system — PII detection, classification, and redaction",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Init
ensure_storage_dirs()
init_db()

# Static file serving for document images
app.mount("/files/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/files/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")
app.mount("/files/redacted", StaticFiles(directory=str(REDACTED_DIR)), name="redacted")

# API routes
app.include_router(router)
