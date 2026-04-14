# SecureMask

SecureMask is a full-stack document privacy system for Indian ID documents.  
It detects sensitive fields, checks context-based necessity, computes a Privacy Exposure Index (PEI), and applies selective redaction.

## What is currently implemented

- **Backend:** FastAPI (`securemask/`)
- **Frontend:** React + Vite (`frontend/`)
- **Storage:** local filesystem + SQLite (`securemask/storage/`)
- **OCR chain:** PaddleOCR → Google Vision fallback (if credentials exist) → EasyOCR fallback
- **Classification:** MobileNetV2 checkpoint (if available) with keyword fallback

## Supported document types

The backend currently supports **5** document types:

1. Aadhaar
2. PAN
3. Passport
4. Driving License
5. Voter ID

## Supported contexts

- `age_verification`
- `identity_verification`
- `address_proof`
- `kyc_onboarding`
- `general_upload`

## API endpoints

| Method | Endpoint           | Purpose |
|---|---|---|
| POST | `/upload` | Upload file + context and run full pipeline |
| POST | `/redact` | Apply redaction decisions and generate audit |
| GET  | `/audit/{scan_id}` | Fetch generated audit report |
| GET  | `/scans` | List scan history |
| POST | `/scan-text` | Detect PII in raw text (no image redaction) |

### Example: upload

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@sample.png" \
  -F "context=kyc_onboarding"
```

### Example: redact

```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "scan_id": "<scan_id>",
    "decisions": {
      "aadhaar_number": "redact",
      "name": "allow",
      "qr_code": "redact"
    }
  }'
```

## Local setup

### 1) Backend setup

Prerequisites:
- Python 3.10+

Install and run:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn securemask.main:app --reload --host 0.0.0.0 --port 8000
```

Backend URLs:
- API base: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

### 2) Frontend setup

Prerequisites:
- Node.js 18+ (recommended)

Install and run:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:
- App: `http://localhost:5173`

Vite dev server proxies:
- `/api/*` → `http://localhost:8000/*`
- `/files/*` → `http://localhost:8000/files/*`

## Project layout

```text
securemask/
├── api/            # FastAPI routes
├── core/           # OCR, classification, extraction, necessity, PEI, redaction
├── db/             # SQLite schema and data access
├── models/         # Dataclasses for scans/fields/audit
├── schemas/        # Per-document extraction schemas
├── ml/             # Classifier training/synthetic utilities
├── config.py
└── main.py

frontend/
├── src/
│   ├── pages/
│   ├── components/
│   ├── api/
│   ├── hooks/
│   └── context/
└── vite.config.js
```

## Notes

- The frontend includes login/signup screens, but auth APIs are currently mocked on the frontend side.
- Uploaded, processed, and redacted files are served by backend static routes under `/files/*`.
