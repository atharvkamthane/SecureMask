"""MobileNetV2 document type classifier.

Loads trained checkpoint from ml/weights/classifier.pth.
Fallback: keyword-based scoring when checkpoint is not available.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms

from securemask.config import CLASS_LABELS, CLASSIFIER_CHECKPOINT

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    document_type: str
    confidence: float
    all_probs: dict[str, float]


# ---------------------------------------------------------------------------
# Keyword fallback scoring — works without trained model
# ---------------------------------------------------------------------------

_KEYWORD_SETS = {
    "aadhaar": {
        "keywords": [
            "aadhaar", "uid", "uidai", "unique identification authority",
            "government of india", "enrolment", "enrollment",
            "आधार", "भारत सरकार", "नाम", "पता", "जन्म",
            "unique identity", "resident", "mera aadhaar", "my aadhaar",
            "माझे आधार", "मेरा आधार",
        ],
        "patterns": [r"\d{4}\s?\d{4}\s?\d{4}"],
    },
    "pan": {
        "keywords": [
            "permanent account number", "pan", "income tax",
            "department", "impot", "govt of india",
            "income tax department", "father's name", "father name",
        ],
        "patterns": [r"[A-Z]{5}[0-9]{4}[A-Z]"],
    },
    "passport": {
        "keywords": [
            "passport", "republic of india", "nationality", "surname",
            "given name", "place of birth", "date of expiry",
            "country code", "ind", "machine readable",
        ],
        "patterns": [r"[A-Z]\d{7}", r"P<IND"],
    },
    "driving_license": {
        "keywords": [
            "driving licence", "driving license", "transport",
            "licence no", "dl no", "blood group", "vehicle class",
            "motor vehicle act", "rto", "regional transport",
            "validity", "cov", "non transport",
        ],
        "patterns": [r"[A-Z]{2}[-\s]?\d{2}[-\s]?(?:(?:19|20)\d{2}[-\s]?)?\d{4,8}"],
    },
    "voter_id": {
        "keywords": [
            "election commission", "elector", "voter id", "epic",
            "photo identity card", "assembly constituency",
            "electoral roll", "polling station", "part no",
            "chief electoral officer",
        ],
        "patterns": [r"[A-Z]{3}\d{7}"],
    },
}


def _keyword_classify(text: str) -> ClassificationResult:
    """Fallback classifier using keyword + pattern matching with calibrated confidence."""
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for doc_type, data in _KEYWORD_SETS.items():
        kw_hits = sum(1 for kw in data["keywords"] if kw.lower() in text_lower)
        pattern_hits = sum(1 for pattern in data["patterns"] if re.search(pattern, text, re.IGNORECASE))

        if kw_hits == 0 and pattern_hits == 0:
            scores[doc_type] = 0.0
            continue

        # Calibrate confidence: pattern match carries strong diagnostic signal
        pattern_conf = min(0.60, pattern_hits * 0.35)
        kw_conf = min(0.40, kw_hits * 0.12)
        total_conf = pattern_conf + kw_conf
        scores[doc_type] = min(1.0, total_conf)

    if not scores or max(scores.values()) == 0.0:
        return ClassificationResult("unknown", 0.0, {})

    best_type = max(scores, key=scores.get)
    best_conf = scores[best_type]

    # Rejection threshold for keyword classification
    if best_conf < 0.20:
        return ClassificationResult("unknown", best_conf, scores)

    return ClassificationResult(best_type, round(best_conf, 3), scores)


# ---------------------------------------------------------------------------
# MobileNetV2 classifier
# ---------------------------------------------------------------------------

class DocumentClassifier:
    """MobileNetV2-based document type classifier with keyword fallback."""

    def __init__(self):
        self._model = None
        self._transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self._label_map: dict[int, str] = {}
        self._loaded = False
        self._load_model()

    def _load_model(self):
        """Load trained checkpoint, or mark as unavailable for keyword fallback."""
        if not CLASSIFIER_CHECKPOINT.exists():
            logger.warning("Classifier checkpoint not found at %s, using keyword fallback", CLASSIFIER_CHECKPOINT)
            return

        try:
            checkpoint = torch.load(CLASSIFIER_CHECKPOINT, map_location="cpu", weights_only=False)
            model = models.mobilenet_v2(weights=None)
            num_classes = len(checkpoint.get("class_labels", CLASS_LABELS))
            model.classifier = torch.nn.Sequential(
                torch.nn.Dropout(0.3),
                torch.nn.Linear(model.last_channel, num_classes),
            )
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            self._model = model

            # Build label map from checkpoint or default
            class_to_idx = checkpoint.get("class_to_idx", {})
            if class_to_idx:
                self._label_map = {v: k for k, v in class_to_idx.items()}
            else:
                labels = checkpoint.get("class_labels", CLASS_LABELS)
                self._label_map = {i: l for i, l in enumerate(labels)}

            self._loaded = True
            val_acc = checkpoint.get("val_accuracy", "?")
            logger.info("Loaded classifier checkpoint (val_acc=%s)", val_acc)

        except Exception as exc:
            logger.error("Failed to load classifier: %s", exc)

    def classify(self, image: Image.Image) -> ClassificationResult:
        """Classify a document image. Uses CNN if available, keyword fallback otherwise."""
        if not self._loaded or self._model is None:
            return ClassificationResult("unknown", 0.0, {})

        try:
            tensor = self._transform(image.convert("RGB")).unsqueeze(0)
            with torch.no_grad():
                logits = self._model(tensor)
                probs = F.softmax(logits, dim=1)
                confidence, class_idx = torch.max(probs, dim=1)

            label = self._label_map.get(class_idx.item(), "unknown")
            conf = float(confidence.item())
            all_probs = {self._label_map.get(i, f"class_{i}"): float(probs[0][i].item())
                         for i in range(probs.shape[1])}

            if conf < 0.55:
                label = "unknown"

            return ClassificationResult(document_type=label, confidence=round(conf, 3), all_probs=all_probs)

        except Exception as exc:
            logger.error("CNN classification failed: %s", exc)
            return ClassificationResult("unknown", 0.0, {})

    def classify_with_text_fallback(self, image: Image.Image, ocr_text: str) -> ClassificationResult:
        """Classify using CNN first; if result is uncertain (<0.65) or unknown, utilize keyword fallback.

        If CNN is uncertain and the keyword classifier has strong diagnostic signal
        (confidence >= 0.45 with distinct class), keyword evidence takes precedence.
        """
        cnn_result = self.classify(image)

        # Trigger keyword classification if CNN is unknown or uncertain
        if cnn_result.document_type == "unknown" or cnn_result.confidence < 0.65:
            kw_result = _keyword_classify(ocr_text)
            if kw_result.document_type != "unknown":
                if cnn_result.document_type == "unknown":
                    logger.info("Classifier: CNN unknown → keyword fallback → %s (conf=%.2f)",
                                kw_result.document_type, kw_result.confidence)
                    return kw_result
                # If CNN was borderline and keyword classifier has strong confidence
                if kw_result.confidence >= 0.45 and kw_result.document_type != cnn_result.document_type:
                    logger.info("Classifier: strong keyword match overrides uncertain CNN (%s [%.2f] > %s [%.2f])",
                                kw_result.document_type, kw_result.confidence, cnn_result.document_type, cnn_result.confidence)
                    return kw_result

        return cnn_result
