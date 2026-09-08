"""QR detection and defensive parsing for Indian identity documents (Aadhaar).

Supports:
1. Fast QR localization for unconditional redaction.
2. Defensive decoding for legacy plain/compressed XML payloads:
   - Decompression bomb protection (enforced payload byte caps).
   - XXE and entity expansion immunity (DOCTYPE stripping and secure XML parsing).
   - Digital signature verification boundary: demographic fields extracted from QR
     are explicitly flagged as unverified (cannot override OCR without cryptographic check).
3. Graceful handling of UIDAI Secure QR binary formats.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
import zlib
from typing import Any

import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar

from securemask.models.detected_field import BoundingBox

logger = logging.getLogger(__name__)

# Security thresholds
MAX_RAW_QR_BYTES = 1024 * 1024       # 1 MB raw cap
MAX_DECOMPRESSED_BYTES = 512 * 1024   # 512 KB decompressed cap


class QRDecoder:
    """Detect QR codes and perform defensive, failure-safe parsing."""

    def detect_qr_regions(self, image: Image.Image) -> list[BoundingBox]:
        """Detect QR code bounding boxes for redaction."""
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            decoded = pyzbar.decode(cv_image)
            boxes: list[BoundingBox] = []
            for item in decoded:
                rect = item.rect
                if rect.width > 5 and rect.height > 5:
                    boxes.append(BoundingBox(int(rect.left), int(rect.top), int(rect.width), int(rect.height)))
            return boxes
        except Exception as exc:
            logger.debug("QR region detection failed: %s", exc)
            return []

    def decode(self, image: Image.Image) -> dict[str, Any] | None:
        """Defensively decode and extract fields from QR payload if valid XML exists.

        Returns demographic dictionary with 'unverified_signature': True,
        or None if payload is binary or unparseable.
        """
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            decoded_items = pyzbar.decode(cv_image)
            if not decoded_items:
                return None

            for item in decoded_items:
                raw_bytes = item.data
                if not raw_bytes or len(raw_bytes) > MAX_RAW_QR_BYTES:
                    logger.warning("QR payload empty or exceeds safe byte limit (%d bytes)", len(raw_bytes))
                    continue

                extracted = self._parse_payload(raw_bytes)
                if extracted:
                    return extracted

            return None
        except Exception as exc:
            logger.debug("QR decode failed: %s", exc)
            return None

    def _parse_payload(self, raw_bytes: bytes) -> dict[str, Any] | None:
        """Safely parse QR byte stream into fields."""
        payload_text = ""

        # Check for zlib/deflate compression
        try:
            decompressor = zlib.decompressobj()
            decompressed = decompressor.decompress(raw_bytes, max_length=MAX_DECOMPRESSED_BYTES)
            payload_text = decompressed.decode("utf-8", errors="ignore")
        except Exception:
            # Fall back to raw string decoding
            payload_text = raw_bytes.decode("utf-8", errors="ignore")

        if not payload_text or "<PrintLetterBarcodeData" not in payload_text:
            logger.info("QR payload is binary/Secure QR format; requires UIDAI public key certificate for signature verification.")
            return None

        return self._safe_parse_xml(payload_text)

    def _safe_parse_xml(self, xml_text: str) -> dict[str, Any] | None:
        """Parse XML with strict XXE, DTD, and entity expansion prevention."""
        try:
            # Defensive sanitation: strip DOCTYPE and ENTITY declarations to eliminate XXE vectors
            sanitized = re.sub(r"<!DOCTYPE[^>]*>", "", xml_text, flags=re.IGNORECASE)
            sanitized = re.sub(r"<!ENTITY[^>]*>", "", sanitized, flags=re.IGNORECASE)

            root = ET.fromstring(sanitized)
            if not root.tag.endswith("PrintLetterBarcodeData") and "PrintLetterBarcodeData" not in root.tag:
                # Find sub-element if nested
                elem = root.find(".//PrintLetterBarcodeData")
                if elem is None:
                    return None
                root = elem

            attrs = root.attrib
            fields: dict[str, Any] = {
                "unverified_signature": True,
                "detection_method": "qr",
            }

            # Map standard UIDAI barcode attributes to canonical fields
            if "uid" in attrs:
                fields["aadhaar_number"] = attrs["uid"]
            if "name" in attrs:
                fields["name"] = attrs["name"]
            if "gender" in attrs:
                fields["gender"] = "Male" if attrs["gender"].upper() == "M" else ("Female" if attrs["gender"].upper() == "F" else attrs["gender"])
            if "dob" in attrs:
                fields["dob"] = attrs["dob"]
            if "yob" in attrs and "dob" not in fields:
                fields["year_of_birth"] = attrs["yob"]

            # Construct structured address if elements exist
            addr_parts = [attrs[k] for k in ("house", "street", "lm", "loc", "vtc", "po", "dist", "state", "pc") if k in attrs and attrs[k]]
            if addr_parts:
                fields["address"] = ", ".join(addr_parts)

            logger.info("Successfully extracted demographic fields from legacy QR (signature unverified)")
            return fields
        except Exception as exc:
            logger.warning("Defensive XML parsing rejected QR payload: %s", exc)
            return None
