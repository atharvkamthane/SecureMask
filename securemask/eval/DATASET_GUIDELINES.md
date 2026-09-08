# SecureMask Ethical Dataset Collection & Curation Guidelines

**Protocol Version:** 1.0 (IEEE Standards & DPDPA 2023 Compliant)  
**Target Domain:** Indian National Identity Documents (Aadhaar, PAN, Passport, Driving License, Voter ID)  
**Repository Path:** `securemask/eval/DATASET_GUIDELINES.md`

---

## 1. Executive Summary & Purpose

SecureMask is designed to protect sensitive personal identifiable information (PII) during identity document submission for commercial and administrative transactions. Evaluating privacy-preserving masking frameworks requires rigorous empirical benchmarking on document layouts. However, national identity credentials represent high-risk personal data subject to stringent regulatory frameworks.

This document establishes the mandatory ethical, legal, and operational protocol for collecting, de-identifying, annotating, and benchmarking identity documents in research and evaluation environments.

---

## 2. Legal & Regulatory Compliance Framework

All document collection and evaluation activities within SecureMask must strictly adhere to the following statutory frameworks:

### 2.1 The Aadhaar (Targeted Delivery of Financial and Other Subsidies, Benefits and Services) Act, 2016
- **Section 29(1):** No core biometric information collected or created under the Act shall be shared with anyone for any reason whatsoever or used for any purpose other than generation of Aadhaar numbers and authentication.
- **Section 29(2):** Identity information (other than core biometrics) may only be shared in accordance with the provisions of this Act and in such manner as specified by regulations.
- **Section 29(4):** No Aadhaar number or core biometric information shall be published, displayed or posted publicly by any person or entity.
- **Evaluation Constraint:** *Unredacted real Aadhaar cards with genuine 12-digit numbers must NEVER be committed to public repositories or shared across unencrypted channels.*

### 2.2 Digital Personal Data Protection Act (DPDPA), 2023
- **Purpose Limitation (Section 5):** Personal data can only be processed for specific lawful purposes for which the Data Principal has given clear and unambiguous consent.
- **Consent Architecture (Section 6):** Consent must be free, specific, informed, unconditional, and unambiguous with clear affirmative action. Consent may be withdrawn at any time.
- **Data Minimization & Storage Limitation (Section 8):** Data fiduciaries must erase personal data as soon as the declared purpose is fulfilled.

### 2.3 Passports Act, 1967 & Motor Vehicles Act, 1988
- Passports contain international Machine Readable Zones (MRZ) governed by ICAO Doc 9303. Unauthorized reproduction and distribution of biometric passport biographical pages are restricted under national security provisions.

---

## 3. Data Collection Protocol & Target Distribution

### 3.1 Target Sample Size & Balance
For statistically valid, peer-reviewed evaluation of document classification and field extraction:
- **Minimum per-class sample:** $\ge 40$ unique documents per category.
- **Categories (5 classes):**
  1. Aadhaar (e-Aadhaar PDF printouts and physical PVC/laminated cards)
  2. Permanent Account Number (PAN) cards (UTIITSL and NSDL formats)
  3. Indian Passport (biographical page / Page 2 and Page 35/36 address page)
  4. Driving License (SARATHI smart card and standard paper/plastic formats)
  5. Voter ID / EPIC (Elector's Photo Identity Card - old and digital e-EPIC formats)
- **Total Minimum Target:** $N \ge 200$ fully annotated, diverse document samples.

### 3.2 Acquisition Condition Diversity
To evaluate real-world robustness (corresponding to Experiment E6):
- **Illumination:** Uniform flat lighting (40%), uneven shadows/glare (30%), low-light mobile capture (30%).
- **Angle / Skew:** Flatbed scan ($0^\circ$, 30%), slight skew ($\pm 5^\circ$ to $\pm 15^\circ$, 40%), perspective tilt ($\ge 15^\circ$, 30%).
- **Resolution:** High-resolution scans ($\ge 300\text{ DPI}$, 40%), standard mobile camera (1080p, 40%), compressed/low-res ($\le 720\text{p}$, 20%).
- **Background Clutter:** Neutral uniform background (50%), complex desktop/fabric background (50%).

---

## 4. Informed Consent Protocol

Document donors must complete and sign an Institutional Review Board (IRB) approved Informed Consent Agreement prior to document acquisition.

### Mandatory Consent Terms:
1. **Explicit Notice:** Donors are informed that documents are collected solely to evaluate automated redaction algorithms.
2. **Opt-in Voluntary Participation:** Donors may withdraw consent at any time without providing justification.
3. **Immediate Synthetic Replacement:** Donors are informed that their actual identifiers (names, numbers, addresses) will be replaced with synthetic pseudo-identities or permanently obscured prior to public distribution or long-term storage.
4. **Data Destruction Guarantee:** Unprocessed original donor images are permanently purged within 30 days of synthetic annotation verification.

---

## 5. De-Identification & Anonymization Pipeline

Before any collected image is committed to internal evaluation sets or shared with collaborators, it must undergo the three-stage de-identification pipeline:

```
[Original Scanned Credential]
             │
             ▼
   [Stage 1: Primary Sanitization]
   - Genuine 12-digit Aadhaar / 10-char PAN / Passport numbers obscured or replaced
   - Real signature replaced with standardized dummy contour
   - Real face replaced with synthetic GAN/diffusion generated portrait
             │
             ▼
   [Stage 2: Sidecar Annotation]
   - Bounding boxes mapped to standardized schema (securemask.eval.annotations_schema)
   - Metadata tagged with acquisition conditions (angle, blur, lighting)
             │
             ▼
   [Stage 3: Verification & Cryptographic Hash]
   - SHA-256 fingerprint logged in evaluation manifest
   - Verification that no live national database record matches the synthetic fields
```

---

## 6. Synthetic Benchmark vs. Real-World Evaluation: Methodological Distinction

In scholarly reporting (IEEE conference and journal submissions), authors must strictly maintain the distinction between:

1. **Synthetic Benchmarks (e.g., `storage/synthetic_benchmark`):**
   - Procedurally generated using standardized layout generators (`generate_synthetic_benchmark.py`).
   - Purpose: Unit testing, regression detection, pipeline integration verification, and controlled ablation studies under ideal visual conditions.
   - Reporting Constraint: Synthetic validation metrics (such as MobileNetV2 100% accuracy) must **never** be presented as real-world generalization.

2. **Real-World Anonymized Testbed:**
   - Acquired under informed consent across real physical cards.
   - Purpose: Primary empirical evidence for classification accuracy, OCR character error rates, field extraction F1-scores, and end-to-end latency.
   - Transparently report sample sizes ($N$), demographic representation, and sensor types.

---

## 7. Storage, Access Control & Incident Response

1. **Access Tiers:**
   - Tier 1 (Raw Donor Images): Stored on encrypted, air-gapped local media with AES-256 full disk encryption. Accessible only to the Principal Investigator.
   - Tier 2 (Sanitized Benchmark Images): Accessible to research team members via authenticated repository access.
2. **Repository Cleanliness:**
   - Git pre-commit hooks verify that no file containing patterns matching live Aadhaar numbers (`^\d{4}\s\d{4}\s\d{4}$`) or unmasked PANs (`^[A-Z]{5}[0-9]{4}[A-Z]$`) can be committed.
3. **Breach Protocol:**
   - If unredacted personal credentials are inadvertently committed, the repository branch must be immediately force-rewritten, cached artifacts invalidated, and affected participants notified within 72 hours per DPDPA Section 8.
