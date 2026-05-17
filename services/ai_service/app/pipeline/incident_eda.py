"""Lightweight exploratory summaries for incident report cohorts."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.domain.incident_category import IncidentCategory


def _parse_ts(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw[:19].replace("T", " ")
    return str(raw)


def _category_labels(row: dict[str, Any]) -> list[str]:
    """Normalize ``category`` enum array into lowercase label strings."""
    raw = row.get("category")
    if raw is None:
        return []
    if isinstance(raw, list):
        labels: list[str] = []
        for x in raw:
            if isinstance(x, IncidentCategory):
                labels.append(x.value)
            elif isinstance(x, str) and x.strip():
                labels.append(x.strip().lower())
        return labels
    if isinstance(raw, str) and raw.strip():
        return [raw.strip().lower()]
    return []


def _custom_category_label(row: dict[str, Any]) -> str | None:
    raw = row.get("custom_category")
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if s else None


def build_incident_eda(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Produce compact JSON-friendly statistics for prompting / transparency.

    Enum categories may appear multiple times per row (multi-label).
    Distributions count label occurrences across rows; ``custom_category`` is
    counted separately.
    """
    n = len(records)
    if n == 0:
        return {
            "record_count": 0,
            "note": "No incident rows in the requested window.",
        }

    category_counts = Counter()
    custom_category_counts = Counter()
    rows_without_category = 0
    rows_with_custom_only = 0
    titles_present = 0

    for r in records:
        labels = _category_labels(r)
        custom = _custom_category_label(r)
        if not labels:
            rows_without_category += 1
        for lab in labels:
            category_counts[lab] += 1
        if custom:
            custom_category_counts[custom] += 1
        if not labels and custom:
            rows_with_custom_only += 1
        if str(r.get("title") or "").strip():
            titles_present += 1

    narratives_missing = sum(
        1 for r in records if not str(r.get("narrative") or "").strip()
    )

    occurred_samples = [_parse_ts(r.get("occurred_at")) for r in records]
    occurred_samples = [x for x in occurred_samples if x]
    occurred_sorted = sorted(occurred_samples) if occurred_samples else []

    return {
        "record_count": n,
        "category_distribution": dict(category_counts.most_common(25)),
        "custom_category_distribution": dict(
            custom_category_counts.most_common(25)
        ),
        "rows_without_category": rows_without_category,
        "rows_with_custom_category_only": rows_with_custom_only,
        "rows_with_title": titles_present,
        "allowed_categories": [c.value for c in IncidentCategory],
        "field_quality": {
            "missing_narrative": narratives_missing,
        },
        "occurred_at_range": {
            "min": occurred_sorted[0] if occurred_sorted else None,
            "max": occurred_sorted[-1] if occurred_sorted else None,
        },
    }
