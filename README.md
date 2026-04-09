# SecureMask

SecureMask is a FastAPI document privacy protection system for Indian identity documents. It ingests JPG, PNG, PDF, or screenshots, extracts OCR text and word boxes, classifies document type, detects PII fields, applies necessity rules for the declared use case, computes a Privacy Exposure Index (PEI), redacts selected regions, and generates a JSON audit report.

## Supported Documents

- Aadhaar Card
- PAN Card
- Driving License
- Passport
- Voter ID / EPIC Card
- Ration Card
- ESIC Card

## Pipeline

1. Document ingestion with PDF-to-image conversion
2. Tesseract OCR text and word-level bounding boxes
3. Keyword scoring document classification
4. Regex, keyword-anchor, image, and optional spaCy NER field extraction
5. Necessity classification for `age_verification`, `identity_verification`, `address_proof`, `kyc_onboarding`, and `general_upload`
6. PEI score computation before and after redaction
7. Plain-English field explanations
8. PIL pixel-level redaction and audit report generation

## Setup

Install Python dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Install system dependencies:

- Tesseract OCR must be installed and available on `PATH`.
- Poppler is required by `pdf2image` for PDF uploads.
- ZBar is recommended for `pyzbar` QR decoding. OpenCV QR detection is used as a fallback when possible.

Run the app:

```bash
uvicorn securemask.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## REST API

`POST /upload`

Multipart form with:

- `file`: JPG, PNG, PDF, or screenshot
- `context`: one of the supported contexts

Returns `scan_id`, document type, confidence, detected fields, and `pei_before`.

`POST /redact`

JSON body:

```json
{
  "scan_id": "uuid",
  "redaction_decisions": {
    "aadhaar_number": "redact",
    "name": "allow"
  }
}
```

Returns `pei_after`, a redacted image URL, and the audit report.

`GET /audit/{scan_id}`

Returns the full audit report JSON.

`GET /scans`

Returns past scans with scan ID, filename, PEI values, timestamp, and document type.

`POST /scan-text`

JSON body:

```json
{
  "text": "Permanent Account Number ABCDE1234F Date of Birth 01/01/1990",
  "context": "identity_verification"
}
```

Returns the scan response plus `highlighted_text`.

## Notes

- If document classification confidence is below `0.5`, SecureMask classifies the document as `unknown` and runs universal regex plus NER fallback.
- For text-only scans, redaction is not available because there is no source image.
- Local storage is written under `storage/`, including SQLite scan history and redacted PNG files.
