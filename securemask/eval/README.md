# SecureMask Evaluation Harness

This module runs the existing SecureMask pipeline against an annotated test
set and produces every metric needed for a research paper's Results section.

**No numbers are fabricated** — every metric comes from actually running the
pipeline against real annotated images.

## Annotation Format

Each test image has a **JSON sidecar** file with the same stem name:

```
test_set/
├── aadhaar_001.jpg
├── aadhaar_001.json     ← annotation
├── pan_002.png
├── pan_002.json         ← annotation
└── ...
```

### JSON Schema

```json
{
  "image_path": "aadhaar_001.jpg",
  "true_document_type": "aadhaar",
  "fields": [
    {
      "field_name": "aadhaar_number",
      "true_value": "2530 0479 3566",
      "bbox": [335, 830, 330, 52]
    },
    {
      "field_name": "name",
      "true_value": "Atharv Murhari Kamthane",
      "bbox": [330, 312, 320, 36]
    },
    {
      "field_name": "dob",
      "true_value": "15/04/2006",
      "bbox": [550, 372, 135, 34]
    }
  ]
}
```

**Fields:**
- `image_path` — filename (resolved relative to the test directory)
- `true_document_type` — one of: `aadhaar`, `pan`, `passport`, `driving_license`, `voter_id`
- `fields[].field_name` — canonical field name matching the pipeline's output
- `fields[].true_value` — ground-truth text value
- `fields[].bbox` — bounding box as `[x, y, width, height]` in pixels

### Creating Annotations

Use the built-in annotation tool:

```bash
python -m securemask.eval.annotate_cli --image-dir path/to/images/
```

This opens each image in an OpenCV window:
- **Click and drag** to draw bounding boxes
- **Press Enter** to label each box (terminal prompts for field name and value)
- **`n`** = save & next image
- **`u`** = undo last box
- **`t`** = change document type
- **`q`** = quit

## Running Evaluations

### Individual Experiments

Each experiment runs standalone:

```bash
# E1: Classification accuracy
python -m securemask.eval.run_e1_classification --test-dir path/to/test_set/

# E2: Field extraction (reports normalized + strict match modes)
python -m securemask.eval.run_e2_extraction --test-dir path/to/test_set/

# E3: OCR engine fallback analysis (EasyOCR primary, PaddleOCR fallback)
python -m securemask.eval.run_e3_ocr_fallback --test-dir path/to/test_set/

# E5: Redaction IoU (Hungarian matching, saves review images)
python -m securemask.eval.run_e5_redaction_iou --test-dir path/to/test_set/

# E6: Robustness under degradation (skew, brightness, occlusion)
python -m securemask.eval.run_e6_robustness --test-dir path/to/test_set/

# E7: End-to-end latency (CPU + GPU if available)
python -m securemask.eval.run_e7_latency --test-dir path/to/test_set/
```

### Full Suite

Run everything at once:

```bash
python -m securemask.eval.run_all --test-dir path/to/test_set/
```

All scripts accept `--output-dir` to override the default output location
(`<test-dir>/eval_results/`).

## Output Files

After `run_all.py`, the output directory contains:

| File                    | Description |
|-------------------------|-------------|
| `results.json`          | Complete structured results for all experiments |
| `results_table.csv`     | Paper Table III: doc_type × accuracy × F1 × IoU × latency |
| `e1_results.json`       | E1 classification details |
| `e1_confusion_matrix.csv` | Confusion matrix |
| `e2_results.json`       | E2 extraction details (includes both normalized and strict match) |
| `e2_extraction.csv`     | Per-field P/R/F1 (paper-ready) |
| `e3_results.json`       | E3 OCR engine analysis |
| `e3_ocr_fallback.csv`   | Per-image engine usage |
| `e5_results.json`       | E5 redaction IoU details |
| `e5_redaction_iou.csv`  | Per-field IoU |
| `review/`               | 20 random redacted images for visual inspection |
| `e6_results.json`       | E6 robustness deltas |
| `e6_robustness.csv`     | Degradation → accuracy delta table |
| `e7_results.json`       | E7 latency (CPU + GPU if available) |
| `e7_latency.csv`        | Latency summary |

## Key Design Decisions

- **E2 match modes**: The headline F1 uses *normalized* matching (whitespace-stripped, case-insensitive). If strict matching differs meaningfully (>1% delta), both are reported in `e2_results.json`.
- **E5 box matching**: Uses Hungarian (optimal) assignment via `scipy.optimize.linear_sum_assignment` to match ground-truth boxes to redacted boxes.
- **E6 ground truth**: Degraded images reuse the exact same annotations as the clean baseline — no separate annotation needed.
- **E7 GPU**: If `torch.cuda.is_available()`, both CPU and GPU latency are reported side by side in all outputs.
- **OCR engine ordering**: EasyOCR is the primary engine; PaddleOCR is the fallback. E3 explicitly labels this in all outputs.

## Testing

Metric calculation functions are tested with synthetic fixtures:

```bash
python -m pytest tests/test_eval_metrics.py -v
```

## Dependencies

In addition to the existing project requirements, E5 requires:

```
scipy>=1.10.0
```
