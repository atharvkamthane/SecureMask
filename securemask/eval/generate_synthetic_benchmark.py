"""Generate a cleanly annotated synthetic benchmark dataset for evaluation harness testing.

Creates synthetic document images paired with exact ground-truth JSON sidecars.
NOTE: This dataset is explicitly designated as SYNTHETIC BENCHMARK data and is used
for verifying pipeline execution, regression testing, and controlled ablations.
It is NOT presented as real-world evaluation evidence.

Usage::
    python -m securemask.eval.generate_synthetic_benchmark --count-per-class 10 --output-dir storage/synthetic_benchmark
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageFont

fake = Faker("en_IN")

CLASSES = ["aadhaar", "pan", "passport", "driving_license", "voter_id"]


def _get_font(size: int = 14, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _generate_synthetic_aadhaar(idx: int, out_dir: Path) -> tuple[Path, dict]:
    w, h = 640, 400
    img = Image.new("RGB", (w, h), (255, 250, 240))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(18, bold=True)
    f_lbl = _get_font(11)
    f_val = _get_font(14, bold=True)
    f_num = _get_font(20, bold=True)

    # Header
    draw.text((70, 20), "Government of India", fill=(0, 0, 0), font=f_title)
    draw.text((70, 45), "भारत सरकार", fill=(80, 80, 80), font=f_lbl)

    name = fake.name()
    dob = f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(1975,2004)}"
    gender = random.choice(["Male", "Female"])
    aadhaar_num = f"{random.randint(2000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"

    # Draw fields and track exact bounding boxes
    fields = []

    # Name
    draw.text((70, 100), "Name:", fill=(100, 100, 100), font=f_lbl)
    draw.text((70, 115), name, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "name", "true_value": name, "bbox": [70, 115, 200, 22]})

    # DOB
    draw.text((70, 150), "DOB:", fill=(100, 100, 100), font=f_lbl)
    draw.text((70, 165), dob, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "dob", "true_value": dob, "bbox": [70, 165, 120, 20]})

    # Gender
    draw.text((220, 150), "Gender:", fill=(100, 100, 100), font=f_lbl)
    draw.text((220, 165), gender, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "gender", "true_value": gender, "bbox": [220, 165, 80, 20]})

    # Number
    draw.text((150, 320), aadhaar_num, fill=(0, 0, 120), font=f_num)
    fields.append({"field_name": "aadhaar_number", "true_value": aadhaar_num, "bbox": [150, 320, 280, 28]})

    # Photo box
    draw.rectangle([480, 90, 600, 250], outline=(150, 150, 150), width=2, fill=(220, 220, 220))
    fields.append({"field_name": "photo", "true_value": "PHOTO_REGION", "bbox": [480, 90, 120, 160]})

    img_path = out_dir / f"aadhaar_syn_{idx:03d}.png"
    img.save(img_path)

    ann = {
        "image_path": str(img_path.name),
        "true_document_type": "aadhaar",
        "is_synthetic_benchmark": True,
        "fields": fields,
    }
    return img_path, ann


def _generate_synthetic_pan(idx: int, out_dir: Path) -> tuple[Path, dict]:
    w, h = 640, 400
    img = Image.new("RGB", (w, h), (240, 248, 255))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(16, bold=True)
    f_lbl = _get_font(11)
    f_val = _get_font(13, bold=True)
    f_num = _get_font(18, bold=True)

    draw.text((60, 20), "INCOME TAX DEPARTMENT", fill=(0, 50, 100), font=f_title)
    draw.text((60, 45), "GOVT. OF INDIA", fill=(100, 100, 100), font=f_lbl)

    name = fake.name().upper()
    fname = fake.first_name().upper() + " " + fake.last_name().upper()
    dob = f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(1975,2002)}"
    chars = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    digits = f"{random.randint(1000,9999)}"
    last_char = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    pan_num = f"{chars}{digits}{last_char}"

    fields = []

    draw.text((50, 90), "NAME / नाम", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 105), name, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "name", "true_value": name, "bbox": [50, 105, 220, 20]})

    draw.text((50, 140), "FATHER'S NAME / पिता का नाम", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 155), fname, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "father_name", "true_value": fname, "bbox": [50, 155, 220, 20]})

    draw.text((50, 190), "DATE OF BIRTH / जन्म की तारीख", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 205), dob, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "dob", "true_value": dob, "bbox": [50, 205, 120, 20]})

    draw.text((50, 250), "Permanent Account Number", fill=(80, 80, 80), font=f_lbl)
    draw.text((50, 268), pan_num, fill=(0, 0, 100), font=f_num)
    fields.append({"field_name": "pan_number", "true_value": pan_num, "bbox": [50, 268, 200, 25]})

    # Photo & signature placeholders
    draw.rectangle([470, 90, 590, 230], outline=(150, 150, 150), width=2, fill=(220, 220, 220))
    fields.append({"field_name": "photo", "true_value": "PHOTO_REGION", "bbox": [470, 90, 120, 140]})

    draw.rectangle([470, 260, 590, 320], outline=(150, 150, 150), width=1, fill=(255, 255, 255))
    draw.text((490, 280), "Signature", fill=(120, 120, 120), font=f_lbl)
    fields.append({"field_name": "signature", "true_value": "SIGNATURE_REGION", "bbox": [470, 260, 120, 60]})

    img_path = out_dir / f"pan_syn_{idx:03d}.png"
    img.save(img_path)

    ann = {
        "image_path": str(img_path.name),
        "true_document_type": "pan",
        "is_synthetic_benchmark": True,
        "fields": fields,
    }
    return img_path, ann


def _generate_synthetic_passport(idx: int, out_dir: Path) -> tuple[Path, dict]:
    w, h = 640, 420
    img = Image.new("RGB", (w, h), (245, 245, 240))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(16, bold=True)
    f_lbl = _get_font(11)
    f_val = _get_font(13, bold=True)
    f_mrz = _get_font(13, bold=True)

    draw.text((60, 20), "REPUBLIC OF INDIA / PASSPORT", fill=(0, 0, 0), font=f_title)

    name = fake.last_name().upper() + " " + fake.first_name().upper()
    pass_num = f"{random.choice('ABCDEFGHJKLMNPRT')}{random.randint(1000000,9999999)}"
    dob = f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(1980,2002)}"
    doe = f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{random.randint(2028,2035)}"

    fields = []

    draw.text((50, 80), "Passport No:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 95), pass_num, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "passport_number", "true_value": pass_num, "bbox": [50, 95, 140, 20]})

    draw.text((50, 130), "Given Name(s):", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 145), name, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "name", "true_value": name, "bbox": [50, 145, 220, 20]})

    draw.text((50, 180), "Date of Expiry:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 195), doe, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "date_of_expiry", "true_value": doe, "bbox": [50, 195, 120, 20]})

    # MRZ lines
    mrz1 = f"P<IND{name.replace(' ', '<<')}"[:44].ljust(44, "<")
    mrz2 = f"{pass_num}6IND{random.randint(100000,999999)}4M{random.randint(100000,999999)}<<<<<<<6"[:44].ljust(44, "<")
    draw.text((40, 340), mrz1, fill=(0, 0, 0), font=f_mrz)
    draw.text((40, 365), mrz2, fill=(0, 0, 0), font=f_mrz)
    fields.append({"field_name": "mrz_lines", "true_value": f"{mrz1}\n{mrz2}", "bbox": [40, 340, 560, 50]})

    img_path = out_dir / f"passport_syn_{idx:03d}.png"
    img.save(img_path)

    ann = {
        "image_path": str(img_path.name),
        "true_document_type": "passport",
        "is_synthetic_benchmark": True,
        "fields": fields,
    }
    return img_path, ann


def _generate_synthetic_dl(idx: int, out_dir: Path) -> tuple[Path, dict]:
    w, h = 640, 400
    img = Image.new("RGB", (w, h), (250, 245, 245))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(16, bold=True)
    f_lbl = _get_font(11)
    f_val = _get_font(13, bold=True)
    f_num = _get_font(16, bold=True)

    draw.text((50, 20), "UNION OF INDIA / DRIVING LICENCE", fill=(120, 20, 20), font=f_title)
    draw.text((50, 42), "MOTOR VEHICLES ACT", fill=(80, 80, 80), font=f_lbl)

    state = random.choice(["MH", "DL", "KA", "TN", "UP"])
    rto = f"{random.randint(1,14):02d}"
    year = f"{random.randint(2010,2023)}"
    seq = f"{random.randint(1000000,9999999)}"
    dl_num = f"{state}{rto} {year}{seq}"
    name = fake.name()
    addr = f"{fake.street_address()}, {fake.city()}"

    fields = []

    draw.text((50, 85), "DL No:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 100), dl_num, fill=(0, 0, 0), font=f_num)
    fields.append({"field_name": "dl_number", "true_value": dl_num, "bbox": [50, 100, 220, 22]})

    draw.text((50, 140), "Name:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 155), name, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "name", "true_value": name, "bbox": [50, 155, 200, 20]})

    draw.text((50, 195), "Address:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 210), addr[:35], fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "address", "true_value": addr[:35], "bbox": [50, 210, 320, 20]})

    img_path = out_dir / f"driving_license_syn_{idx:03d}.png"
    img.save(img_path)

    ann = {
        "image_path": str(img_path.name),
        "true_document_type": "driving_license",
        "is_synthetic_benchmark": True,
        "fields": fields,
    }
    return img_path, ann


def _generate_synthetic_voter_id(idx: int, out_dir: Path) -> tuple[Path, dict]:
    w, h = 640, 400
    img = Image.new("RGB", (w, h), (240, 250, 245))
    draw = ImageDraw.Draw(img)

    f_title = _get_font(16, bold=True)
    f_lbl = _get_font(11)
    f_val = _get_font(13, bold=True)
    f_num = _get_font(16, bold=True)

    draw.text((50, 20), "ELECTION COMMISSION OF INDIA", fill=(0, 80, 40), font=f_title)
    draw.text((50, 42), "ELECTOR PHOTO IDENTITY CARD", fill=(80, 80, 80), font=f_lbl)

    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
    digits = f"{random.randint(1000000,9999999)}"
    epic_num = f"{letters}{digits}"
    name = fake.name()

    fields = []

    draw.text((50, 85), "EPIC No:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 100), epic_num, fill=(0, 0, 0), font=f_num)
    fields.append({"field_name": "epic_number", "true_value": epic_num, "bbox": [50, 100, 160, 22]})

    draw.text((50, 140), "Elector's Name:", fill=(100, 100, 100), font=f_lbl)
    draw.text((50, 155), name, fill=(0, 0, 0), font=f_val)
    fields.append({"field_name": "name", "true_value": name, "bbox": [50, 155, 200, 20]})

    img_path = out_dir / f"voter_id_syn_{idx:03d}.png"
    img.save(img_path)

    ann = {
        "image_path": str(img_path.name),
        "true_document_type": "voter_id",
        "is_synthetic_benchmark": True,
        "fields": fields,
    }
    return img_path, ann


def generate_benchmark(count_per_class: int, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files: list[Path] = []

    generators = {
        "aadhaar": _generate_synthetic_aadhaar,
        "pan": _generate_synthetic_pan,
        "passport": _generate_synthetic_passport,
        "driving_license": _generate_synthetic_dl,
        "voter_id": _generate_synthetic_voter_id,
    }

    print(f"Generating synthetic benchmark dataset ({count_per_class} per class, total {count_per_class * len(CLASSES)})...")
    for doc_type, gen_func in generators.items():
        for i in range(1, count_per_class + 1):
            img_path, ann = gen_func(i, output_dir)
            json_path = img_path.with_suffix(".json")
            json_path.write_text(json.dumps(ann, indent=2, ensure_ascii=False), encoding="utf-8")
            generated_files.append(img_path)

    print(f"Generated {len(generated_files)} synthetic benchmark images with annotations in: {output_dir}")
    return generated_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic benchmark dataset.")
    parser.add_argument("--count-per-class", type=int, default=10, help="Number of images per class (default: 10)")
    parser.add_argument("--output-dir", type=Path, default=Path("storage/synthetic_benchmark"), help="Output directory")
    args = parser.parse_args()

    random.seed(42)
    generate_benchmark(args.count_per_class, args.output_dir)


if __name__ == "__main__":
    main()
