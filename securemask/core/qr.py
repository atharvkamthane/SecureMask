"""QR code decoder for Aadhaar cards.

Aadhaar QR encodes resident XML data. Decodes using pyzbar,
parses XML (handles both raw XML and zlib-compressed newer format).
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
import zlib

import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar

from securemask.models.detected_field import BoundingBox

logger = logging.getLogger(__name__)


class QRDecoder:
    """Decode QR codes from document images, with Aadhaar XML parsing."""

    def decode(self, image: Image.Image) -> dict | None:
        """Decode Aadhaar QR code and return parsed fields.

        Returns dict with: aadhaar_number, name, dob, gender, address, phone.
        Or None if no valid QR found.
        """
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            decoded = pyzbar.decode(cv_image)

            if not decoded:
                return None

            raw = decoded[0].data

            # Try direct XML parse
            root = None
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                # Try decompressing (newer Aadhaar QR is zlib compressed)
                try:
                    decompressed = zlib.decompress(raw, -zlib.MAX_WBITS)
                    root = ET.fromstring(decompressed)
                except Exception:
                    # Try with different wbits
                    try:
                        decompressed = zlib.decompress(raw)
                        root = ET.fromstring(decompressed)
                    except Exception:
                        logger.debug("QR data is not parseable XML")
                        return None

            if root is None:
                return None

            return {
                "aadhaar_number": root.attrib.get("uid", ""),
                "name": root.attrib.get("name", ""),
                "dob": root.attrib.get("dob", ""),
                "gender": root.attrib.get("gender", ""),
                "address": self._build_address(root),
                "phone": root.attrib.get("mobile", ""),
            }

        except Exception as exc:
            logger.debug("QR decode failed: %s", exc)
            return None

    def _build_address(self, root: ET.Element) -> str:
        """Build address string from Aadhaar QR XML attributes."""
        parts = [
            root.attrib.get("house"),
            root.attrib.get("street"),
            root.attrib.get("lm"),
            root.attrib.get("loc"),
            root.attrib.get("vtc"),
            root.attrib.get("dist"),
            root.attrib.get("state"),
            root.attrib.get("pc"),
        ]
        return ", ".join(filter(None, parts))

    def detect_qr_regions(self, image: Image.Image) -> list[BoundingBox]:
        """Detect QR code bounding boxes for redaction."""
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            decoded = pyzbar.decode(cv_image)
            boxes = []
            for item in decoded:
                rect = item.rect
                boxes.append(BoundingBox(rect.left, rect.top, rect.width, rect.height))
            return boxes
        except Exception:
            return []
