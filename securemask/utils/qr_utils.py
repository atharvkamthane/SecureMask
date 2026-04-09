from __future__ import annotations

from PIL import Image

from securemask.models.detected_field import BoundingBox


def detect_qr_codes(image: Image.Image) -> list[BoundingBox]:
    boxes: list[BoundingBox] = []
    try:
        from pyzbar.pyzbar import decode

        for item in decode(image):
            rect = item.rect
            boxes.append(BoundingBox(rect.left, rect.top, rect.width, rect.height))
        if boxes:
            return boxes
    except Exception:
        pass

    try:
        import cv2
        import numpy as np

        detector = cv2.QRCodeDetector()
        arr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        ok, points = detector.detect(arr)
        if ok and points is not None:
            pts = points.astype(int).reshape(-1, 2)
            x, y = pts[:, 0].min(), pts[:, 1].min()
            right, bottom = pts[:, 0].max(), pts[:, 1].max()
            boxes.append(BoundingBox(int(x), int(y), int(right - x), int(bottom - y)))
    except Exception:
        pass
    return boxes
