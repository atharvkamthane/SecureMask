# SecureMask — Document Privacy Protection System

SecureMask detects personally identifiable information (PII) in uploaded Indian identity documents, classifies the document type, runs a necessity check based on declared use-case context, computes a Privacy Exposure Index (PEI) score, and allows users to mask/redact sensitive fields before downloading a safe version of the document.

## Supported Document Types

| # | Document            | Key Fields Detected                          |
|---|---------------------|----------------------------------------------|
| 1 | Aadhaar Card        | Aadhaar number, name, DOB, gender, address, phone, QR code |
| 2 | PAN Card            | PAN number, name, father's name, DOB, signature |
| 3 | Driving License     | DL number, name, DOB, address, blood group, vehicle class, validity |
| 4 | Passport            | Passport number, name, nationality, DOB, place of birth/issue, MRZ lines |
| 5 | Voter ID (EPIC)     | EPIC number, name, father/husband name, DOB, gender, address, constituency |
| 6 | Ration Card         | Card number, head of family, family members, address, category |
| 7 | ESIC Card           | Insurance number, name, DOB, dispensary, employer, family members |

## Pipeline Stages

1. **Document Ingestion** — Accept JPG, PNG, PDF, screenshots
2. **OCR Extraction** — Tesseract OCR (primary) with EasyOCR fallback; word-level bounding boxes
3. **Document Classification** — Keyword scoring classifier with confidence threshold
4. **PII Field Extraction** — Regex + keyword anchor + NER extraction per document type
5. **Necessity Classification** — Context-based required/excess field lookup
6. **PEI Computation** — Privacy Exposure Index score 0–100
7. **Explainability** — Plain-English explanations for each flagged field
8. **Redaction Engine** — Pixel-level black box masking with QR/signature detection

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn
- **OCR:** pytesseract (primary), EasyOCR (fallback)
- **NLP/NER:** spaCy with `en_core_web_sm`
- **Image Processing:** OpenCV, Pillow (PIL), pyzbar
- **PDF Handling:** pdf2image
- **Database:** SQLite
- **Frontend:** Vanilla HTML/CSS/JS

## Setup

### Prerequisites

- Python 3.10 or later
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and in PATH
  - Windows: Download installer from [UB-Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki)
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`
- [Poppler](https://poppler.freedesktop.org/) for PDF support (used by `pdf2image`)
  - Windows: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/) and add `bin/` to PATH
  - Ubuntu/Debian: `sudo apt install poppler-utils`
  - macOS: `brew install poppler`

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd SecureMask

# Create virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Running the Server

```bash
# Start the FastAPI server
uvicorn securemask.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

- **API Docs (Swagger):** `http://localhost:8000/docs`
- **Frontend UI:** `http://localhost:8000/`

## API Endpoints

| Method | Endpoint           | Description                                    |
|--------|--------------------|------------------------------------------------|
| POST   | `/upload`          | Upload document image + context, get scan results |
| POST   | `/redact`          | Apply redaction decisions and download safe image |
| GET    | `/audit/{scan_id}` | Retrieve full audit report for a scan           |
| GET    | `/scans`           | List all past scans                             |
| POST   | `/scan-text`       | Scan raw text input (no image redaction)        |

### POST /upload

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@aadhaar.png" \
  -F "context=kyc_onboarding"
```

### POST /redact

```bash
curl -X POST http://localhost:8000/redact \
  -H "Content-Type: application/json" \
  -d '{
    "scan_id": "<scan_id>",
    "redaction_decisions": {
      "aadhaar_number": "redact",
      "name": "allow",
      "qr_code": "redact"
    }
  }'
```

### POST /scan-text

```bash
curl -X POST http://localhost:8000/scan-text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Aadhaar Number: 1234 5678 9012, Name: Rahul Kumar",
    "context": "identity_verification"
  }'
```

## Supported Contexts

| Context                | Description                          |
|------------------------|--------------------------------------|
| `age_verification`     | Only age-related fields required     |
| `identity_verification`| Core identity fields required        |
| `address_proof`        | Address fields required              |
| `kyc_onboarding`       | Full KYC field set required          |
| `general_upload`       | No fields required — all flagged     |

## Privacy Exposure Index (PEI)

PEI is a score from 0–100 (higher = more privacy risk). It accounts for:
- Sensitivity weight of each detected field (1–10)
- Whether each field is **required** or **excess** for the declared context
- Fields not required for the context incur full penalty
- Required fields incur minor exposure cost

After redaction, PEI is recomputed counting only fields marked as `"allow"`.

## Project Structure

```
securemask/
├── main.py                 # FastAPI entry point
├── config.py               # Constants, field schemas, supported contexts
├── core/
│   ├── ocr.py              # OCR extraction with bounding boxes
│   ├── classifier.py       # Document type classifier (keyword scoring)
│   ├── extractor.py        # Field extraction (regex + NER + keyword anchor)
│   ├── necessity.py        # Necessity matrix lookup
│   ├── pei.py              # PEI formula computation
│   ├── explainer.py        # Explainability string generation
│   ├── redactor.py         # Image redaction engine
│   └── audit.py            # Audit report generation
├── schemas/
│   ├── aadhaar.py          # Aadhaar field schema + regex
│   ├── pan.py              # PAN field schema + regex
│   ├── driving_license.py  # DL field schema + regex
│   ├── passport.py         # Passport field schema + regex
│   ├── voter_id.py         # Voter ID field schema + regex
│   ├── ration_card.py      # Ration Card field schema + regex
│   └── esic.py             # ESIC field schema + regex
├── models/
│   ├── detected_field.py   # DetectedField + BoundingBox dataclasses
│   ├── audit_report.py     # AuditReport dataclass
│   └── scan.py             # ScanSession dataclass
├── api/
│   └── routes.py           # REST API route handlers
├── db/
│   ├── database.py         # SQLite connection + schema init
│   └── crud.py             # CRUD operations for scans
└── utils/
    ├── image_utils.py      # PDF→image, OCR preprocessing, zone bounds
    └── qr_utils.py         # QR code detection (pyzbar + OpenCV)
```

## License

MIT
