"""
Concatenate incident fields into a single document for vectorisation.

Each row becomes one bag-of-words input to TF-IDF (title, enum categories,
custom category, narrative). See ``INCIDENT_REPORTS.md`` § Document construction.
"""

from __future__ import annotations

from typing import Any

from app.pipeline.incident_eda import (
    _category_labels,
    _custom_category_label,
)


def build_incident_document_text(row: dict[str, Any]) -> str:
    """
    Build one space-separated document string from a db-service incident row.

    Category enums and custom labels are included so structured tags influence
    topics even when narratives are short. Lowercasing happens in
    ``incident_topic_modelling._clean_document``.
    """
    parts: list[str] = []
    title = str(row.get("title") or "").strip()
    if title:
        parts.append(title)
    labels = _category_labels(row)
    if labels:
        parts.extend(labels)
    custom = _custom_category_label(row)
    if custom:
        parts.append(custom)
    narrative = str(row.get("narrative") or "").strip()
    if narrative:
        parts.append(narrative)
    return " ".join(parts)
