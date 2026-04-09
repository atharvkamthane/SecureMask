from __future__ import annotations

from securemask.schemas import SCHEMA_MODULES


def classify_document(text: str) -> tuple[str, float, dict[str, float]]:
    normalized = " ".join(text.lower().split())
    scores: dict[str, float] = {}
    for document_type, module in SCHEMA_MODULES.items():
        keywords = getattr(module, "DOCUMENT_KEYWORDS", [])
        if not keywords:
            scores[document_type] = 0.0
            continue
        matches = sum(1 for keyword in keywords if keyword.lower() in normalized)
        scores[document_type] = matches / len(keywords)

    if not scores:
        return "unknown", 0.0, {}
    best_doc, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score < 0.3:
        return "unknown", round(best_score, 3), scores
    return best_doc, round(best_score, 3), scores
