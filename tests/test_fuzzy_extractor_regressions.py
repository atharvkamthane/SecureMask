from __future__ import annotations

import os

os.environ["SECUREMASK_SKIP_OCR_PREWARM"] = "1"

import unittest
from unittest import mock

from PIL import Image

from securemask.core.extractor import FieldExtractor, _fuzzy, _preprocess_ocr_text
from securemask.core.fuzzy_regex import FuzzyRegexExtractor, _clean_for_digits
from securemask.core.ocr import OCRResult, OCRWord
from securemask.models.detected_field import BoundingBox
from securemask.schemas import get_schema


def _make_words(tokens: list[str]) -> list[OCRWord]:
    words: list[OCRWord] = []
    for index, token in enumerate(tokens):
        words.append(
            OCRWord(
                text=token,
                confidence=0.9,
                bbox=BoundingBox(index * 12, 0, max(8, len(token) * 6), 12),
            )
        )
    return words


class FuzzyRegexRegressionTest(unittest.TestCase):
    def test_proximity_does_not_block_clean_exact_match(self):
        extractor = FuzzyRegexExtractor()
        aadhaar = "2530 0479 3566"
        text = "aadhaar " + ("x " * 120) + aadhaar
        words = _make_words(["aadhaar"] + ["x"] * 120 + aadhaar.split())

        value, confidence, bbox = extractor.extract(
            text=text,
            pattern=r"\b\d{4}\s?\d{4}\s?\d{4}\b",
            threshold=85,
            words=words,
            anchor_keywords=["aadhaar", "आधार"],
        )

        self.assertEqual(value, aadhaar)
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(confidence, 0.88)

    def test_digit_cleaning_only_targets_numeric_tokens(self):
        self.assertEqual(_clean_for_digits("253O"), "2530")
        self.assertEqual(_clean_for_digits("Office"), "Office")

    def test_digit_cleaning_recovers_ocr_misread_digits(self):
        extractor = FuzzyRegexExtractor()
        text = "253O 0479 3566"
        words = _make_words(text.split())

        value, confidence, bbox = extractor.extract(
            text=text,
            pattern=r"\b\d{4}\s?\d{4}\s?\d{4}\b",
            threshold=85,
            words=words,
            anchor_keywords=[],
        )

        self.assertEqual(value, "2530 0479 3566")
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(confidence, 0.88)


class ExtractorRegressionTest(unittest.TestCase):
    def test_schema_regex_uses_cleaned_ocr_first(self):
        field_extractor = FieldExtractor()
        schema = next(s for s in get_schema("aadhaar") if s.field_name == "aadhaar_number")

        raw = OCRResult(
            full_text="253O 0479 3566",
            words=_make_words(["253O", "0479", "3566"]),
            image_width=200,
            image_height=60,
        )
        cleaned = _preprocess_ocr_text(raw)
        image = Image.new("RGB", (200, 60), "white")

        with mock.patch.object(_fuzzy, "extract", return_value=(None, 0.0, None)) as mock_extract:
            field_extractor._extract_field(
                schema,
                raw,
                cleaned,
                image,
                image_path=None,
                qr_data=None,
                mrz_data=None,
                document_type="aadhaar",
            )

        self.assertGreaterEqual(mock_extract.call_count, 2)
        self.assertEqual(mock_extract.call_args_list[0].args[0], cleaned.full_text)
        self.assertEqual(mock_extract.call_args_list[1].args[0], raw.full_text)

    def test_aadhaar_broad_scan_recovers_uid_and_dob(self):
        field_extractor = FieldExtractor()
        raw = OCRResult(
            full_text="Aadhaar 2530 0479 3566 DOB 01/02/1990",
            words=_make_words(["Aadhaar", "2530", "0479", "3566", "DOB", "01/02/1990"]),
            image_width=300,
            image_height=100,
        )
        image = Image.new("RGB", (300, 100), "white")

        with mock.patch.object(field_extractor, "_extract_field", return_value=None), \
             mock.patch("securemask.core.extractor._qr.decode", return_value=None):
            results = field_extractor.extract(raw, image, "aadhaar", image_path=None)

        field_map = {field.field_name: field.field_value for field in results}
        self.assertEqual(field_map.get("aadhaar_number"), "2530 0479 3566")
        self.assertEqual(field_map.get("dob"), "01/02/1990")


if __name__ == "__main__":
    unittest.main()