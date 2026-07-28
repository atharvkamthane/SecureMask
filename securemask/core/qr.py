"""QR detection for Aadhaar cards.

Current UIDAI Secure QR payloads are signed binary data, not plain XML. This
module therefore detects their region for redaction but deliberately does not
turn an unverified QR payload into authoritative identity fields.
"""
from __future__ import annotations

import logging

import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar

from securemask.models.detected_field import BoundingBox

logger = logging.getLogger(__name__)


class QRDecoder:
    """Detect QR codes and reserve demographic decoding for a verified reader."""

    def decode(self, image: Image.Image) -> dict | None:
        """Return no demographics until UIDAI signature verification is available.

        ``pyzbar`` exposes bytes only; it cannot verify UIDAI's digital
        signature or decode the current secure-QR binary format. Returning
        fields from arbitrary XML-like bytes would let an untrusted QR override
        OCR results with fabricated personal data.
        """
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            decoded = pyzbar.decode(cv_image)
            if decoded:
                logger.info("Aadhaar QR detected; skipping unverified demographic extraction")
            return None

        except Exception as exc:
            logger.debug("QR decode failed: %s", exc)
            return None

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
