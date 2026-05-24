from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np


class OcrFixesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SECUREMASK_SKIP_OCR_PREWARM"] = "1"
        cls.ocr = importlib.import_module("securemask.core.ocr")

    def test_extract_paddle_items_supports_dict_results(self):
        res = {
            "rec_texts": ["Aadhaar", "1234"],
            "rec_scores": [0.91, 0.84],
            "dt_polys": [
                [(10, 11), (50, 11), (50, 30), (10, 30)],
                [(60, 11), (100, 11), (100, 30), (60, 30)],
            ],
        }

        items = self.ocr._extract_paddle_items(res)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][0], "Aadhaar")
        self.assertAlmostEqual(items[0][1], 0.91, places=2)
        self.assertEqual(items[0][2][0], (10, 11))

    def test_parse_paddle_result_materialises_generator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            image = np.full((80, 160, 3), 255, dtype=np.uint8)
            cv2.imwrite(str(image_path), image)

            def result_generator():
                yield {
                    "rec_texts": ["Name", "Rahul"],
                    "rec_scores": [0.95, 0.93],
                    "dt_polys": [
                        [(5, 5), (35, 5), (35, 20), (5, 20)],
                        [(40, 5), (80, 5), (80, 20), (40, 20)],
                    ],
                }

            parsed = self.ocr._parse_paddle_result(result_generator(), str(image_path))

            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.full_text, "Name Rahul")
            self.assertEqual(len(parsed.words), 2)
            self.assertEqual(parsed.image_width, 160)
            self.assertEqual(parsed.image_height, 80)

    def test_engine_routes_color_image_to_easyocr(self):
        engine = self.ocr.OCREngine()

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "raw.png"
            color_path = Path(tmpdir) / "color.jpg"
            gray_path = Path(tmpdir) / "gray.png"
            image = np.full((64, 128, 3), 255, dtype=np.uint8)
            cv2.imwrite(str(raw_path), image)
            cv2.imwrite(str(color_path), image)
            cv2.imwrite(str(gray_path), cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))

            captured = {}

            def fake_paddle(path, force_hindi=False):
                captured["paddle_path"] = path
                return None

            def fake_easyocr(path):
                captured["easy_path"] = path
                return self.ocr.OCRResult(
                    full_text="Aadhaar 1234 India",
                    words=[
                        self.ocr.OCRWord("Aadhaar", 0.9, self.ocr.BoundingBox(1, 1, 10, 10)),
                        self.ocr.OCRWord("1234", 0.9, self.ocr.BoundingBox(12, 1, 10, 10)),
                        self.ocr.OCRWord("India", 0.9, self.ocr.BoundingBox(24, 1, 10, 10)),
                    ],
                    image_width=128,
                    image_height=64,
                )

            with mock.patch.object(self.ocr, "_paddle_ocr", side_effect=fake_paddle), \
                 mock.patch.object(self.ocr, "_easyocr_fallback", side_effect=fake_easyocr):
                result = engine.extract(
                    str(raw_path),
                    preprocessed_color_path=str(color_path),
                    preprocessed_gray_path=str(gray_path),
                )

            self.assertEqual(captured["easy_path"], str(color_path))
            self.assertEqual(captured.get("paddle_path"), None)
            self.assertEqual(result.full_text, "Aadhaar 1234 India")


if __name__ == "__main__":
    unittest.main()
