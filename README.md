# SecureMask — Document Privacy Protection System

SecureMask is an AI-powered Document Privacy Protection System that detects personally identifiable information (PII) in Indian identity documents, classifies the document type using a trained CNN, evaluates data necessity based on declared context, computes a Privacy Exposure Index (PEI) score, and enables pixel-level redaction of sensitive fields before download.

## Supported Document Types

| # | Document            | Key Fields Detected                                                    |
|---|---------------------|------------------------------------------------------------------------|
| 1 | Aadhaar Card        | Aadhaar number, name, DOB, gender, address, phone, QR code            |
| 2 | PAN Card            | PAN number, name, father's name, DOB, signature                       |
| 3 | Driving Licence     | DL number, name, DOB, address, blood group                            |
| 4 | Passport            | Passport number, name, DOB, place of birth, expiry, father/spouse, MRZ|
| 5 | Voter ID (EPIC)     | EPIC number, name, father/husband name, DOB, gender, address          |

## Pipeline Stages

1. **Document Ingestion** — Accept JPG, PNG, PDF uploads
2. **Preprocessing** — Deskew → Grayscale → Denoise → CLAHE → Otsu binarization (OpenCV)
3. **OCR Extraction** — **PaddleOCR** (primary) → **Google Cloud Vision API** (fallback 1) → **EasyOCR** (fallback 2); word-level bounding boxes
4. **Document Classification** — **MobileNetV2 CNN** (primary, PyTorch, trained on synthetic data) → Keyword/pattern scoring (fallback)
5. **PII Field Extraction** — Multi-engine:
   - QR code decoding (pyzbar) — Aadhaar XML parsing with zlib decompression
   - MRZ parsing (passporteye / regex fallback) — Passport MRZ Type 3
   - Regex + fuzzy matching (rapidfuzz) — sliding window + keyword-anchored search
   - NER (HuggingFace IndicNER / spaCy `en_core_web_sm` fallback) — names, addresses, dates
   - Image detection (Haar cascade face detection, QR region, signature region)
6. **Necessity Classification** — 5-context × 5-document-type matrix (required vs excess fields)
7. **PEI Computation** — Privacy Exposure Index score 0–100 with sensitivity weighting
8. **Explainability** — Method-aware plain-English explanations per flagged field
9. **Redaction Engine** — Pixel-level black-box masking with partial-mask mode support

## Tech Stack

### Backend
- **Framework:** Python 3.10+, FastAPI, Uvicorn
- **OCR:** PaddleOCR (primary), Google Cloud Vision API, EasyOCR
- **ML/Classification:** PyTorch (MobileNetV2 fine-tuned), torchvision
- **NLP/NER:** HuggingFace Transformers (ai4bharat/IndicNER), spaCy (`en_core_web_sm`)
- **Image Processing:** OpenCV (preprocessing, face detection), Pillow (redaction), pyzbar (QR)
- **Fuzzy Matching:** rapidfuzz
- **Database:** SQLite (raw `sqlite3`)
- **Data Generation:** Faker (synthetic training data)

### Frontend
- **Framework:** React 19 + Vite 8
- **Styling:** Tailwind CSS v4
- **Animation:** Framer Motion
- **Charts:** Recharts
- **Routing:** React Router v7
- **Icons:** Lucide React
- **HTTP:** Axios (proxied to FastAPI via Vite dev server)

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Cloud Vision API credentials (optional, for OCR fallback)
  - Save service account JSON as `securemask-493217-2bd77a5a45c8.json` in root

### Backend Installation

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# Install Python dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Frontend Installation

```bash
cd frontend
npm install
```

### Running the Application

**Terminal 1 — Backend (port 8000):**
```bash
uvicorn securemask.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend (port 5173):**
```bash
cd frontend
npm run dev
```

- **Frontend UI:** `http://localhost:5173`
- **API Docs (Swagger):** `http://localhost:8000/docs`
- **API Base:** `http://localhost:8000` (proxied via Vite at `/api/*`)

## API Endpoints

| Method | Endpoint             | Description                                      |
|--------|----------------------|--------------------------------------------------|
| POST   | `/upload`            | Upload document image + context, run full pipeline|
| POST   | `/redact`            | Apply redaction decisions, generate safe image    |
| GET    | `/audit/{scan_id}`   | Retrieve full audit report (DPDP Act + GDPR)     |
| GET    | `/scans`             | List all past scan summaries                      |
| POST   | `/scan-text`         | Scan raw text input for PII (no image)            |

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
    "decisions": {
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

PEI is a score from 0–100 (higher = more privacy risk). Formula:

- **always_redact fields:** full penalty (`weight × 10`)
- **Excess fields** (not required for context): full penalty (`weight × 10`)
- **Required fields:** minor exposure cost (`weight × 2`)
- **PEI = (raw_score / max_possible) × 100**

After redaction, PEI is recomputed counting only fields marked as `"allow"`.

## Compliance

Audit reports include compliance notes referencing:
- **India's Digital Personal Data Protection Act 2023** (Section 6 — lawful purpose, consent, data minimisation)
- **GDPR Article 5(1)(c)** (data minimisation principle)

## Project Structure

```
SecureMask/
├── securemask/                  # Python backend
│   ├── main.py                  # FastAPI entry point (v2.0.0)
│   ├── config.py                # Paths, constants, supported contexts, universal regex
│   ├── __init__.py              # Package init + version
│   ├── api/
│   │   └── routes.py            # REST endpoints + Pydantic response models
│   ├── core/
│   │   ├── ocr.py               # PaddleOCR → Google Vision → EasyOCR chain
│   │   ├── classifier.py        # MobileNetV2 CNN + keyword fallback
│   │   ├── extractor.py         # Multi-engine field extraction coordinator
│   │   ├── fuzzy_regex.py       # Regex + rapidfuzz sliding-window matcher
│   │   ├── mrz.py               # Passport MRZ parser (passporteye + regex)
│   │   ├── ner.py               # HuggingFace IndicNER + spaCy NER
│   │   ├── qr.py                # pyzbar QR decoder + Aadhaar XML parser
│   │   ├── preprocessor.py      # OpenCV image preprocessing pipeline
│   │   ├── necessity.py         # 5×5 necessity matrix
│   │   ├── pei.py               # PEI scoring formula
│   │   ├── explainer.py         # Method-aware explanations
│   │   ├── redactor.py          # PIL-based image redaction (black box + partial mask)
│   │   └── audit.py             # Audit report builder
│   ├── schemas/
│   │   ├── base.py              # FieldSchema dataclass
│   │   ├── aadhaar.py           # Aadhaar field definitions + regex
│   │   ├── pan.py               # PAN field definitions + regex
│   │   ├── passport.py          # Passport field definitions + MRZ
│   │   ├── driving_license.py   # DL field definitions + regex
│   │   └── voter_id.py          # Voter ID field definitions + regex
│   ├── models/
│   │   ├── detected_field.py    # DetectedField + BoundingBox dataclasses
│   │   ├── audit_report.py      # AuditReport + ComplianceNotes dataclasses
│   │   └── scan.py              # ScanSession dataclass
│   ├── ml/
│   │   ├── train_classifier.py  # MobileNetV2 fine-tuning (20 epochs, cosine LR)
│   │   ├── generate_synthetic.py# Synthetic document image generator (Faker + PIL)
│   │   └── weights/
│   │       └── classifier.pth   # Trained model checkpoint (~9 MB)
│   ├── db/
│   │   ├── database.py          # SQLite connection + schema init
│   │   └── crud.py              # CRUD operations for scans
│   └── utils/
│       ├── image_utils.py       # PIL/OpenCV conversion helpers
│       └── confidence.py        # Confidence aggregation helpers
│
├── frontend/                    # React + Vite + Tailwind CSS
│   ├── src/
│   │   ├── App.jsx              # Router + providers (Auth, Scan, Motion)
│   │   ├── main.jsx             # React root
│   │   ├── index.css            # Tailwind + custom design tokens
│   │   ├── api/                 # Axios API clients
│   │   ├── components/
│   │   │   ├── ui/              # Reusable: Button, Card, Modal, Badge, etc.
│   │   │   ├── domain/          # PEIGauge, FieldCard, DocumentPreview, etc.
│   │   │   ├── landing/         # Hero, FeatureCards, HowItWorks, etc.
│   │   │   └── layout/          # AppShell, TopNav, Footer
│   │   ├── pages/               # Landing, Upload, Detection, PEI, Redaction, Audit, etc.
│   │   ├── hooks/               # usePEI, useRedaction, useScan, etc.
│   │   ├── context/             # AuthContext, ScanContext
│   │   ├── constants/           # Context/docType definitions
│   │   └── utils/               # Field helpers, PEI color logic
│   ├── vite.config.js           # Vite + Tailwind + API proxy to :8000
│   └── package.json             # React 19, Framer Motion, Recharts, etc.
│
├── storage/                     # Runtime data (gitignored)
│   ├── uploads/                 # User-uploaded documents
│   ├── processed/               # Preprocessed images
│   ├── redacted/                # Redacted output images
│   └── securemask.sqlite3       # SQLite database
│
├── requirements.txt             # Python dependencies
├── .gitignore
└── README.md
```

## ML Training (Optional)

To retrain the document classifier:

```bash
# Generate synthetic training data (1250 images, ~23 MB)
python -m securemask.ml.generate_synthetic

# Train MobileNetV2 (20 epochs, saves best checkpoint)
python -m securemask.ml.train_classifier
```

## License

MIT
