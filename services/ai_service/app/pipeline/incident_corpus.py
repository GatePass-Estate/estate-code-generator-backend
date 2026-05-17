"""Shared text extraction from incident report rows."""

from __future__ import annotations

from typing import Any

from app.pipeline.incident_eda import (
    _category_labels,
    _custom_category_label,
)


def build_incident_document_text(row: dict[str, Any]) -> str:
    """
    Single document string for topic modelling (title, labels, narrative).

    Lowercasing is applied later; this only concatenates fields.
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
