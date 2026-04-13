"""Synthetic document image generator for training MobileNetV2 classifier.

Generates 250 images per document class (5 classes = 1250 total).
Each image is a PIL-rendered fake document with:
  - Correct aspect ratio and background colour
  - Government logo placeholder
  - Field labels in correct positions
  - Format-valid fake field values (Faker)
  - Realistic noise: slight rotation, JPEG compression, slight blur
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageFont, ImageFilter

fake = Faker("en_IN")

# Output directory
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "synthetic_data"

CLASSES = ["aadhaar", "pan", "passport", "driving_license", "voter_id"]
IMAGES_PER_CLASS = 250
TRAIN_SPLIT = 200


def _random_color(base_r: int, base_g: int, base_b: int, spread: int = 20) -> tuple:
    return (
        max(0, min(255, base_r + random.randint(-spread, spread))),
        max(0, min(255, base_g + random.randint(-spread, spread))),
        max(0, min(255, base_b + random.randint(-spread, spread))),
    )


def _get_font(size: int = 14, bold: bool = False):
    """Try to load a TrueType font; fall back to default."""
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_logo_placeholder(draw: ImageDraw.Draw, x: int, y: int, size: int = 40, color=(180, 180, 180)):
    """Draw a simple circle + lines as a logo placeholder."""
    draw.ellipse([x, y, x + size, y + size], outline=color, width=2)
    draw.line([x + size // 4, y + size // 2, x + 3 * size // 4, y + size // 2], fill=color, width=1)
    draw.line([x + size // 2, y + size // 4, x + size // 2, y + 3 * size // 4], fill=color, width=1)


def _add_noise(img: Image.Image) -> Image.Image:
    """Add realistic noise: rotation, blur, JPEG compression artifacts."""
    # Slight rotation (±3°)
    angle = random.uniform(-3, 3)
    img = img.rotate(angle, expand=False, fillcolor=(255, 255, 255))

    # Slight blur
    if random.random() > 0.5:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 0.8)))

    # JPEG compression artifacts
    from io import BytesIO
    buf = BytesIO()
    quality = random.randint(60, 95)
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    return img


def _generate_aadhaar(index: int) -> Image.Image:
    """Generate a synthetic Aadhaar card image."""
    w, h = 640, 400
    bg = _random_color(255, 250, 240, 10)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(18, bold=True)
    label_font = _get_font(11)
    value_font = _get_font(14, bold=True)
    number_font = _get_font(22, bold=True)

    # Header
    _draw_logo_placeholder(draw, 20, 15, 35, (200, 50, 50))
    draw.text((70, 18), "Government of India", fill=(0, 0, 0), font=title_font)
    draw.text((70, 40), "भारत सरकार", fill=(80, 80, 80), font=label_font)

    _draw_logo_placeholder(draw, w - 60, 15, 35, (50, 100, 200))
    draw.text((w - 180, 18), "UID / आधार", fill=(50, 100, 200), font=title_font)

    # Photo placeholder
    draw.rectangle([30, 80, 170, 240], outline=(150, 150, 150), width=2)
    draw.text((70, 150), "PHOTO", fill=(180, 180, 180), font=label_font)

    # Name
    name = fake.name()
    draw.text((190, 85), "Name / नाम", fill=(100, 100, 100), font=label_font)
    draw.text((190, 100), name, fill=(0, 0, 0), font=value_font)

    # DOB
    dob = fake.date_of_birth(minimum_age=18, maximum_age=80).strftime("%d/%m/%Y")
    draw.text((190, 130), "DOB / जन्म तिथि", fill=(100, 100, 100), font=label_font)
    draw.text((190, 145), dob, fill=(0, 0, 0), font=value_font)

    # Gender
    gender = random.choice(["MALE", "FEMALE", "पुरुष", "महिला"])
    draw.text((400, 130), "Gender / लिंग", fill=(100, 100, 100), font=label_font)
    draw.text((400, 145), gender, fill=(0, 0, 0), font=value_font)

    # Address
    addr = fake.address().replace("\n", ", ")[:80]
    draw.text((190, 175), "Address / पता", fill=(100, 100, 100), font=label_font)
    draw.text((190, 190), addr[:50], fill=(0, 0, 0), font=label_font)
    if len(addr) > 50:
        draw.text((190, 205), addr[50:], fill=(0, 0, 0), font=label_font)

    # Aadhaar number
    num = f"{random.randint(1000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}"
    draw.text((w // 2 - 80, h - 90), num, fill=(0, 0, 0), font=number_font)

    # QR placeholder
    qr_size = 80
    draw.rectangle([w - qr_size - 20, h - qr_size - 30, w - 20, h - 30],
                    outline=(100, 100, 100), width=2)
    draw.text((w - qr_size - 10, h - qr_size // 2 - 30), "QR", fill=(150, 150, 150), font=label_font)

    # Bottom text
    draw.text((20, h - 25), "माझे आधार, माझी ओळख", fill=(180, 50, 50), font=label_font)

    return _add_noise(img)


def _generate_pan(index: int) -> Image.Image:
    w, h = 550, 350
    bg = _random_color(255, 248, 230, 8)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(16, bold=True)
    label_font = _get_font(10)
    value_font = _get_font(13, bold=True)
    pan_font = _get_font(20, bold=True)

    # Header
    _draw_logo_placeholder(draw, 20, 10, 30, (0, 0, 128))
    draw.text((60, 12), "INCOME TAX DEPARTMENT", fill=(0, 0, 128), font=title_font)
    draw.text((60, 32), "GOVT. OF INDIA", fill=(80, 80, 80), font=label_font)
    draw.text((w // 2 - 60, 55), "PERMANENT ACCOUNT NUMBER CARD", fill=(0, 0, 0), font=label_font)

    # Photo
    draw.rectangle([w - 130, 80, w - 30, 210], outline=(150, 150, 150), width=2)

    # Name
    name = fake.name().upper()
    draw.text((30, 85), "Name", fill=(100, 100, 100), font=label_font)
    draw.text((30, 100), name, fill=(0, 0, 0), font=value_font)

    # Father's name
    fname = fake.name_male().upper()
    draw.text((30, 130), "Father's Name", fill=(100, 100, 100), font=label_font)
    draw.text((30, 145), fname, fill=(0, 0, 0), font=value_font)

    # DOB
    dob = fake.date_of_birth(minimum_age=18, maximum_age=80).strftime("%d/%m/%Y")
    draw.text((30, 175), "Date of Birth", fill=(100, 100, 100), font=label_font)
    draw.text((30, 190), dob, fill=(0, 0, 0), font=value_font)

    # PAN number
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    pan = f"{''.join(random.choices(letters, k=5))}{random.randint(1000,9999)}{random.choice(letters)}"
    draw.text((w // 2 - 50, h - 80), pan, fill=(0, 0, 128), font=pan_font)

    # Signature area
    draw.text((30, h - 50), "Signature", fill=(100, 100, 100), font=label_font)
    draw.line([30, h - 35, 180, h - 35], fill=(150, 150, 150), width=1)

    return _add_noise(img)


def _generate_passport(index: int) -> Image.Image:
    w, h = 600, 420
    bg = _random_color(240, 245, 255, 8)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(16, bold=True)
    label_font = _get_font(9)
    value_font = _get_font(12, bold=True)
    mrz_font = _get_font(11)

    # Header
    draw.text((w // 2 - 60, 10), "REPUBLIC OF INDIA", fill=(0, 0, 128), font=title_font)
    _draw_logo_placeholder(draw, w // 2 - 15, 30, 30, (0, 0, 128))
    draw.text((w // 2 - 30, 68), "PASSPORT", fill=(0, 0, 128), font=title_font)

    # Photo
    draw.rectangle([30, 100, 170, 270], outline=(150, 150, 150), width=2)

    # Fields
    pnum = f"{random.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{random.randint(1,9)}{random.randint(1000000,9999999)}"
    surname = fake.last_name().upper()
    given = fake.first_name().upper()
    dob = fake.date_of_birth(minimum_age=18, maximum_age=70).strftime("%d/%m/%Y")
    pob = fake.city().upper()
    doe = fake.date_between(start_date="+1y", end_date="+10y").strftime("%d/%m/%Y")

    y = 100
    for label, val in [("Passport No.", pnum), ("Surname", surname),
                       ("Given Name(s)", given), ("Date of Birth", dob),
                       ("Place of Birth", pob), ("Date of Expiry", doe)]:
        draw.text((190, y), label, fill=(100, 100, 100), font=label_font)
        draw.text((190, y + 12), val, fill=(0, 0, 0), font=value_font)
        y += 28

    # MRZ lines
    mrz1 = "P<IND" + surname + "<<" + given + "<" * (44 - 5 - len(surname) - 2 - len(given))
    mrz2 = pnum + "0IND" + "0" * 20 + "<" * (44 - len(pnum) - 24)
    draw.text((20, h - 55), mrz1[:44], fill=(0, 0, 0), font=mrz_font)
    draw.text((20, h - 38), mrz2[:44], fill=(0, 0, 0), font=mrz_font)

    return _add_noise(img)


def _generate_driving_license(index: int) -> Image.Image:
    w, h = 550, 350
    bg = _random_color(245, 250, 255, 10)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(14, bold=True)
    label_font = _get_font(10)
    value_font = _get_font(12, bold=True)

    states = ["MH", "DL", "KA", "TN", "UP", "GJ", "RJ", "MP", "WB", "AP"]
    state = random.choice(states)

    draw.text((w // 2 - 80, 10), "DRIVING LICENCE", fill=(180, 0, 0), font=title_font)
    draw.text((w // 2 - 50, 30), "TRANSPORT DEPT", fill=(80, 80, 80), font=label_font)

    # Photo
    draw.rectangle([w - 120, 60, w - 30, 180], outline=(150, 150, 150), width=2)

    dl_num = f"{state}{random.randint(10,99)}{random.randint(10000,99999)}{random.randint(1000,9999)}"
    name = fake.name()
    dob = fake.date_of_birth(minimum_age=18, maximum_age=65).strftime("%d/%m/%Y")
    addr = fake.address().replace("\n", ", ")[:60]
    bg_val = random.choice(["A+", "B+", "O+", "AB+", "A-", "O-"])

    y = 60
    for label, val in [("DL No.", dl_num), ("Name", name), ("DOB", dob),
                       ("Address", addr), ("Blood Group", bg_val)]:
        draw.text((30, y), label, fill=(100, 100, 100), font=label_font)
        draw.text((30, y + 14), val, fill=(0, 0, 0), font=value_font)
        y += 35

    return _add_noise(img)


def _generate_voter_id(index: int) -> Image.Image:
    w, h = 550, 350
    bg = _random_color(255, 255, 245, 8)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    title_font = _get_font(14, bold=True)
    label_font = _get_font(10)
    value_font = _get_font(12, bold=True)

    draw.text((w // 2 - 90, 10), "ELECTION COMMISSION OF INDIA", fill=(0, 100, 0), font=title_font)
    _draw_logo_placeholder(draw, w // 2 - 15, 30, 28, (0, 100, 0))
    draw.text((w // 2 - 60, 65), "ELECTOR'S PHOTO IDENTITY CARD", fill=(0, 0, 0), font=label_font)

    # Photo
    draw.rectangle([w - 120, 90, w - 30, 220], outline=(150, 150, 150), width=2)

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    epic = f"{''.join(random.choices(letters, k=3))}{random.randint(1000000,9999999)}"
    name = fake.name()
    fname = fake.name_male()
    dob = fake.date_of_birth(minimum_age=18, maximum_age=80).strftime("%d/%m/%Y")
    gender = random.choice(["Male", "Female"])
    addr = fake.address().replace("\n", ", ")[:60]

    y = 90
    for label, val in [("EPIC No.", epic), ("Elector's Name", name),
                       ("Father's Name", fname), ("Date of Birth", dob),
                       ("Gender", gender), ("Address", addr[:50])]:
        draw.text((30, y), label, fill=(100, 100, 100), font=label_font)
        draw.text((30, y + 14), val, fill=(0, 0, 0), font=value_font)
        y += 32

    return _add_noise(img)


GENERATORS = {
    "aadhaar": _generate_aadhaar,
    "pan": _generate_pan,
    "passport": _generate_passport,
    "driving_license": _generate_driving_license,
    "voter_id": _generate_voter_id,
}


def generate_all():
    """Generate all synthetic images, split into train/val folders."""
    for cls_name in CLASSES:
        train_dir = DATA_DIR / "train" / cls_name
        val_dir = DATA_DIR / "val" / cls_name
        train_dir.mkdir(parents=True, exist_ok=True)
        val_dir.mkdir(parents=True, exist_ok=True)

        gen = GENERATORS[cls_name]
        print(f"Generating {IMAGES_PER_CLASS} images for '{cls_name}'...")

        for i in range(IMAGES_PER_CLASS):
            img = gen(i)
            if i < TRAIN_SPLIT:
                img.save(train_dir / f"{cls_name}_{i:04d}.jpg", "JPEG", quality=90)
            else:
                img.save(val_dir / f"{cls_name}_{i:04d}.jpg", "JPEG", quality=90)

    total = IMAGES_PER_CLASS * len(CLASSES)
    print(f"\nDone! Generated {total} images -> {DATA_DIR}")
    print(f"  Train: {TRAIN_SPLIT * len(CLASSES)}")
    print(f"  Val:   {(IMAGES_PER_CLASS - TRAIN_SPLIT) * len(CLASSES)}")


if __name__ == "__main__":
    generate_all()
