# Experiment E4: Human Privacy Perception Study Guide

This document contains 12 evaluation scenarios and a structured rating sheet template for conducting the **E4 Privacy Exposure Index (PEI) Human Validation Study**.

---

## Instructions for the Study Administrator

1. Share the **12 Scenarios** and **Rating Form** (below) with **3 to 5 independent human raters**.
2. Raters should evaluate the perceived privacy risk for each scenario on a scale from **1 (Very Low Risk)** to **10 (Critical Exposure Risk)**.
3. Collect the responses and compute the mean human risk score per scenario.
4. Compare human scores against SecureMask's calculated **PEI scores** using Pearson/Spearman correlation ($r$ and $\rho$).

---

## 12 Evaluation Scenarios

### Scenario 1: Age Verification (Aadhaar)
* **Context**: Uploading an ID to verify age (>18) on an online gaming website.
* **Document**: Aadhaar Card.
* **Unredacted Fields**: Name, Date of Birth, Gender, Address, Aadhaar Number, Photo.
* **Redacted Fields**: None (Full unredacted document uploaded).

### Scenario 2: Minimal Age Verification (Aadhaar - SecureMask Redacted)
* **Context**: Uploading an ID to verify age (>18) on an online gaming website.
* **Document**: Aadhaar Card.
* **Unredacted Fields**: Date of Birth.
* **Redacted Fields**: Name, Gender, Address, Aadhaar Number, Photo, QR Code.

### Scenario 3: Identity Verification (PAN Card - Fully Exposed)
* **Context**: Submitting an ID for hotel check-in desk registration.
* **Document**: PAN Card.
* **Unredacted Fields**: Name, Father's Name, DOB, PAN Number, Photo, Signature.
* **Redacted Fields**: None.

### Scenario 4: Identity Verification (PAN Card - SecureMask Redacted)
* **Context**: Submitting an ID for hotel check-in desk registration.
* **Document**: PAN Card.
* **Unredacted Fields**: Name, PAN Number.
* **Redacted Fields**: Father's Name, DOB, Photo, Signature.

### Scenario 5: Address Proof (Driving License - Unredacted)
* **Context**: Submitting proof of residency to a local ISP for broadband connection.
* **Document**: Driving License.
* **Unredacted Fields**: Name, Address, DL Number, DOB, Blood Group, Photo.
* **Redacted Fields**: None.

### Scenario 6: Address Proof (Driving License - SecureMask Redacted)
* **Context**: Submitting proof of residency to a local ISP for broadband connection.
* **Document**: Driving License.
* **Unredacted Fields**: Name, Address.
* **Redacted Fields**: DL Number, DOB, Blood Group, Photo.

### Scenario 7: KYC Onboarding (Passport - Unredacted)
* **Context**: Complete KYC onboarding for a bank account opening.
* **Document**: Passport.
* **Unredacted Fields**: Name, Passport Number, Nationality, DOB, Place of Birth, Date of Expiry, MRZ lines.
* **Redacted Fields**: None.

### Scenario 8: KYC Onboarding (Passport - Masked Identifier)
* **Context**: Complete KYC onboarding for a bank account opening.
* **Document**: Passport.
* **Unredacted Fields**: Name, Passport Number (first 6 digits masked, last 2 visible), Date of Expiry.
* **Redacted Fields**: Place of Birth, MRZ lines, Photo.

### Scenario 9: General File Upload (Voter ID - Unredacted)
* **Context**: Uploading a document to a public cloud portal for general event registration.
* **Document**: Voter ID (EPIC).
* **Unredacted Fields**: Name, EPIC Number, Relative's Name, Gender, DOB, Address, Photo.
* **Redacted Fields**: None.

### Scenario 10: General File Upload (Voter ID - SecureMask Redacted)
* **Context**: Uploading a document to a public cloud portal for general event registration.
* **Document**: Voter ID (EPIC).
* **Unredacted Fields**: Name.
* **Redacted Fields**: EPIC Number, Relative's Name, Gender, DOB, Address, Photo.

### Scenario 11: Excess Disclosure (Aadhaar for Address Proof - Unredacted)
* **Context**: Uploading an ID solely to prove address for utility bill change.
* **Document**: Aadhaar Card.
* **Unredacted Fields**: Name, Address, Aadhaar Number, Gender, DOB, Photo, QR Code.
* **Redacted Fields**: None.

### Scenario 12: Minimal Disclosure (Aadhaar for Address Proof - SecureMask Redacted)
* **Context**: Uploading an ID solely to prove address for utility bill change.
* **Document**: Aadhaar Card.
* **Unredacted Fields**: Address.
* **Redacted Fields**: Name, Aadhaar Number, Gender, DOB, Photo, QR Code.

---

## Human Rating Sheet Template (CSV / Excel format)

Give raters the following table layout to fill out:

```csv
Rater_ID,Scenario_ID,Perceived_Privacy_Risk_Score_1_to_10,Comments
Rater1,Scenario 1,,
Rater1,Scenario 2,,
Rater1,Scenario 3,,
Rater1,Scenario 4,,
Rater1,Scenario 5,,
Rater1,Scenario 6,,
Rater1,Scenario 7,,
Rater1,Scenario 8,,
Rater1,Scenario 9,,
Rater1,Scenario 10,,
Rater1,Scenario 11,,
Rater1,Scenario 12,,
```

---

## Metric Calculation Script for E4 (`calculate_e4_correlation.py`)

Once raters submit their scores, you can run the following calculation to get Pearson $r$ and Spearman $\rho$:

```python
import numpy as np
from scipy.stats import pearsonr, spearmanr

# Example: Average human rating per scenario (1 to 12)
human_ratings = [9.2, 2.1, 8.8, 3.4, 8.5, 2.8, 9.5, 4.2, 9.8, 1.8, 9.0, 2.0]

# SecureMask PEI scores calculated by compute_pei() for each scenario
pei_scores    = [95.0, 20.0, 90.0, 35.0, 85.0, 25.0, 98.0, 40.0, 100.0, 15.0, 92.0, 18.0]

r, p_val_r = pearsonr(human_ratings, pei_scores)
rho, p_val_rho = spearmanr(human_ratings, pei_scores)

print(f"Pearson Correlation (r):   {r:.4f} (p-value: {p_val_r:.4e})")
print(f"Spearman Correlation (rho): {rho:.4f} (p-value: {p_val_rho:.4e})")
```
