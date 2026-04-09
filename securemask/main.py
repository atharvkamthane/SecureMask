from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from securemask.api.routes import router
from securemask.config import BASE_DIR, REDACTED_DIR, STATIC_DIR, ensure_storage_dirs
from securemask.db.database import init_db


app = FastAPI(title="SecureMask", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_storage_dirs()
init_db()
app.include_router(router)
app.mount("/files/redacted", StaticFiles(directory=REDACTED_DIR), name="redacted-files")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"name": "SecureMask", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok", "storage": str(BASE_DIR / "storage")}
