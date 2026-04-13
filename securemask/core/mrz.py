"""Passport MRZ parser — best-effort with graceful fallback.

Uses passporteye if available, otherwise falls back to regex-based
MRZ line extraction from OCR text.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def _try_passporteye(image_path: str | Path) -> dict | None:
    """Try passporteye MRZ reading."""
    try:
        from passporteye import read_mrz
        mrz = read_mrz(str(image_path))
        if mrz is None:
            return None
        data = mrz.to_dict()
        name = f"{data.get('surname', '')} {data.get('names', '')}".strip().replace("<", " ").strip()
        return {
            "passport_number": data.get("number", "").replace("<", ""),
            "name": name,
            "dob": data.get("date_of_birth", ""),
            "date_of_expiry": data.get("expiry_date", ""),
            "nationality": data.get("nationality", ""),
            "gender": data.get("sex", ""),
            "mrz_lines": data.get("raw_text", ""),
        }
    except ImportError:
        logger.info("passporteye not installed — using regex MRZ fallback")
        return None
    except Exception as exc:
        logger.warning("passporteye MRZ failed: %s", exc)
        return None


def _regex_mrz_from_text(ocr_text: str) -> dict | None:
    """Fallback: extract MRZ lines from OCR text using regex."""
    # MRZ Type 3 (passport): two lines of 44 characters each
    mrz_pattern = r"([A-Z0-9<]{44})\s*\n?\s*([A-Z0-9<]{44})"
    match = re.search(mrz_pattern, ocr_text)
    if not match:
        # Try individual lines
        lines = re.findall(r"[A-Z0-9<]{40,44}", ocr_text)
        if len(lines) >= 2:
            line1, line2 = lines[0][:44], lines[1][:44]
        else:
            return None
    else:
        line1, line2 = match.group(1), match.group(2)

    try:
        # Parse line 1: P<NATIONALITY_SURNAME<<GIVEN_NAMES<<<<
        if not line1.startswith("P"):
            return None
        name_part = line1[5:]  # skip "P<XXX"
        parts = name_part.split("<<")
        surname = parts[0].replace("<", " ").strip() if parts else ""
        given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
        name = f"{surname} {given}".strip()

        # Parse line 2: NUMBER<CHECK_NATIONALITY_DOB_CHECK_SEX_DOE_CHECK_...
        passport_number = line2[:9].replace("<", "")
        nationality = line2[10:13].replace("<", "")
        dob_raw = line2[13:19]
        sex = line2[20]
        doe_raw = line2[21:27]

        # Convert dates YYMMDD → DD/MM/YYYY
        def _convert_date(raw: str) -> str:
            if len(raw) == 6 and raw.isdigit():
                yy, mm, dd = int(raw[:2]), raw[2:4], raw[4:6]
                century = 19 if yy > 40 else 20
                return f"{dd}/{mm}/{century}{yy:02d}"
            return raw

        return {
            "passport_number": passport_number,
            "name": name,
            "dob": _convert_date(dob_raw),
            "date_of_expiry": _convert_date(doe_raw),
            "nationality": nationality,
            "gender": {"M": "Male", "F": "Female"}.get(sex, sex),
            "mrz_lines": f"{line1}\n{line2}",
        }
    except Exception as exc:
        logger.warning("Regex MRZ parsing failed: %s", exc)
        return None


class MRZParser:
    """MRZ parser: passporteye primary → regex fallback."""

    def parse(self, image_path: str | Path | None = None,
              ocr_text: str = "") -> dict | None:
        """Parse MRZ from image or OCR text.

        Returns dict with: passport_number, name, dob, date_of_expiry,
        nationality, gender, mrz_lines. Or None if no MRZ found.
        """
        # Try passporteye on the image
        if image_path:
            result = _try_passporteye(image_path)
            if result:
                return result

        # Fallback to regex on OCR text
        if ocr_text:
            return _regex_mrz_from_text(ocr_text)

        return None
