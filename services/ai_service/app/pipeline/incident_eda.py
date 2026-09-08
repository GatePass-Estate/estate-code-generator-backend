"""
Exploratory descriptive statistics for incident cohorts.

Counts category labels, custom categories, field completeness, and occurred-at
range. Also builds the result-page category EDA (top five + remainder) and a
string-formatted trends line.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Literal

from app.domain.incident_category import IncidentCategory

PeakTime = Literal["morning", "afternoon", "evening_night"]
_TOP_N = 5
_SNIPPET_LEN = 160
_SAMPLE_N = 2


def _parse_ts(raw: Any) -> str | None:
    """
    Normalize ``occurred_at`` to a sortable ``YYYY-MM-DD HH:MM:SS``.

    Arguments:
        raw: Datetime string or other value from an incident row.

    Returns:
        A truncated timestamp string, or ``None`` when ``raw`` is
        empty.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw[:19].replace("T", " ")
    return str(raw)


_FIXED_CATEGORIES = {item.value for item in IncidentCategory}


def _category_labels(row: dict[str, Any]) -> list[str]:
    """
    Return only fixed taxonomy labels from ``category``.

    Arguments:
        row: One incident dict from db-service.

    Returns:
        Lowercased ``IncidentCategory`` values. Unknown strings and
        custom text are dropped.
    """
    raw = row.get("category")
    if raw is None:
        return []
    values: list[str] = []
    if isinstance(raw, list):
        for x in raw:
            if isinstance(x, IncidentCategory):
                values.append(x.value)
            elif isinstance(x, str) and x.strip():
                values.append(x.strip().lower())
    elif isinstance(raw, str) and raw.strip():
        values.append(raw.strip().lower())
    return [label for label in values if label in _FIXED_CATEGORIES]


def _custom_category_label(row: dict[str, Any]) -> str | None:
    """
    Return the trimmed custom-category string, if any.

    Arguments:
        row: One incident dict from db-service.

    Returns:
        Lowercased custom text, or ``None`` when blank.
    """
    raw = row.get("custom_category")
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if s else None


def build_incident_eda(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build descriptive cohort statistics for the LLM prompt and stats.

    Multi-label rows increment each fixed category separately. Custom
    labels are counted in ``custom_category_distribution`` only. Not
    used by TF-IDF/NMF.

    Arguments:
        records: Incident rows in the requested window.

    Returns:
        Record counts, category / custom distributions, field
        quality, and the occurred-at range. An empty window returns
        a note instead of zeros-only distributions.
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


def _occurred_hour(raw: Any) -> int | None:
    """
    Extract the hour of ``occurred_at`` when the value is parseable.

    Arguments:
        raw: A ``datetime`` or ISO-8601 string, possibly with ``Z``.

    Returns:
        Hour in ``0..23``, or ``None`` if parsing fails.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.hour
    text = str(raw).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).hour
    except ValueError:
        return None


def _peak_bucket(hour: int) -> PeakTime:
    """
    Map an hour onto morning / afternoon / evening-night.

    Morning is 06–12, afternoon 12–18, otherwise evening/night.

    Arguments:
        hour: Hour of day in ``0..23``.

    Returns:
        One of ``morning``, ``afternoon``, ``evening_night``.
    """
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "evening_night"


def _snippet(row: dict[str, Any]) -> str:
    """
    Build a short title + narrative excerpt for a sample report.

    Arguments:
        row: One incident dict from db-service.

    Returns:
        Combined text, truncated to ``_SNIPPET_LEN`` characters.
    """
    title = str(row.get("title") or "").strip()
    narrative = str(row.get("narrative") or "").strip()
    if title and narrative:
        body = f"{title}: {narrative}"
    else:
        body = title or narrative
    if len(body) > _SNIPPET_LEN:
        return body[: _SNIPPET_LEN - 1].rstrip() + "…"
    return body


def _row_labels(row: dict[str, Any]) -> list[str]:
    """
    Return the fixed taxonomy labels used for category ranking.

    Arguments:
        row: One incident dict from db-service.

    Returns:
        The same labels as ``_category_labels``; custom text is
        ignored.
    """
    return _category_labels(row)


def _category_item(
    *,
    category: str,
    count: int,
    total: int,
    hours: list[int],
    snippets: list[str],
) -> dict[str, Any]:
    """
    Build one ranked category's peak time, share, and snippets.

    Arguments:
        category: Fixed taxonomy label.
        count: Incidents tagged with this label.
        total: Cohort size used for ``percentage_share``.
        hours: ``occurred_at`` hours for peak-time voting.
        snippets: Pre-built sample excerpts.

    Returns:
        A dict matching ``CategoryEdaItem``.
    """
    buckets: Counter[PeakTime] = Counter()
    for hour in hours:
        buckets[_peak_bucket(hour)] += 1
    peak: PeakTime = "afternoon"
    if buckets:
        peak = buckets.most_common(1)[0][0]
    share = round((count / total) * 100.0, 2) if total else 0.0
    return {
        "category": category,
        "peak_time": peak,
        "incident_count": count,
        "percentage_share": share,
        "sample_reports": snippets[:_SAMPLE_N],
    }


def build_category_eda(records: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Rank fixed taxonomy categories and split top five from the rest.

    Custom-category text is ignored. Top five are ``top_1`` … ``top_5``
    (null when fewer than five labels exist). Remaining labels sit
    under ``other_categories``, still ordered by count descending.
    Each item has peak time, count, percentage of all reports, and
    two snippets.

    Arguments:
        records: Incident rows in the requested window.

    Returns:
        ``top_1`` … ``top_5`` plus ``other_categories``. An empty
        cohort returns null tops and an empty remainder map.
    """
    empty = {
        "top_1": None,
        "top_2": None,
        "top_3": None,
        "top_4": None,
        "top_5": None,
        "other_categories": {},
    }
    total = len(records)
    if total == 0:
        return empty

    counts: Counter[str] = Counter()
    hours: dict[str, list[int]] = defaultdict(list)
    snippets: dict[str, list[str]] = defaultdict(list)
    for row in records:
        labels = _row_labels(row)
        hour = _occurred_hour(row.get("occurred_at"))
        sample = _snippet(row)
        for label in labels:
            counts[label] += 1
            if hour is not None:
                hours[label].append(hour)
            if sample and len(snippets[label]) < _SAMPLE_N:
                snippets[label].append(sample)

    ranked = counts.most_common()
    out = dict(empty)
    for index, (label, count) in enumerate(ranked[:_TOP_N]):
        out[f"top_{index + 1}"] = _category_item(
            category=label,
            count=count,
            total=total,
            hours=hours[label],
            snippets=snippets[label],
        )
    other: dict[str, Any] = {}
    for label, count in ranked[_TOP_N:]:
        other[label] = _category_item(
            category=label,
            count=count,
            total=total,
            hours=hours[label],
            snippets=snippets[label],
        )
    out["other_categories"] = other
    return out


def format_incident_trends(
    *,
    record_count: int,
    category_eda: dict[str, Any],
    stats: dict[str, Any] | None = None,
) -> str:
    """
    Build a one-paragraph trend line from category EDA and stats.

    Arguments:
        record_count: Total incidents in the window.
        category_eda: Output of ``build_category_eda``.
        stats: Optional ``build_incident_eda`` payload for the
            uncategorised-row count.

    Returns:
        A single formatted sentence (or short paragraph).
    """
    if record_count <= 0:
        return "No incident reports matched this estate and date window."
    top = category_eda.get("top_1") if isinstance(category_eda, dict) else None
    noun = "report" if record_count == 1 else "reports"
    if not isinstance(top, dict):
        return (
            f"{record_count} incident {noun} in this window, with no "
            "categorised labels to rank."
        )
    name = str(top.get("category") or "unknown").replace("_", " ")
    count = int(top.get("incident_count") or 0)
    share = top.get("percentage_share")
    peak = str(top.get("peak_time") or "afternoon").replace("_", "/")
    labelled = sum(
        1
        for key in ("top_1", "top_2", "top_3", "top_4", "top_5")
        if category_eda.get(key)
    )
    other = category_eda.get("other_categories") or {}
    if isinstance(other, dict):
        labelled += len(other)
    missing = int((stats or {}).get("rows_without_category") or 0)
    parts = [
        f"{record_count} incident {noun} in this window.",
        (
            f"{name} is the most frequent category "
            f"({count} report{'s' if count != 1 else ''}"
            f"{f', {share}% of the total' if share is not None else ''}), "
            f"peaking in the {peak}."
        ),
        f"{labelled} categor{'y' if labelled == 1 else 'ies'} observed.",
    ]
    if missing:
        verb = "has" if missing == 1 else "have"
        parts.append(
            f"{missing} report{'s' if missing != 1 else ''} "
            f"{verb} no taxonomy category."
        )
    return " ".join(parts)
