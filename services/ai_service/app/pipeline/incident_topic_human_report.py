"""
Presentation layer for NMF topics: friendly names, shares, and plain-text reports.

Maps latent topic keywords to operator-facing theme titles via rule tables,
deduplicates redundant n-grams, and formats ``report_text``. Does not change
the underlying factorisation; see ``explainer_docs/INCIDENT_REPORT_SUMMARY_EXPLAINER.md``.
"""

from __future__ import annotations

from typing import Any

# (keyword fragments, display name) — first match wins.
_THEME_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("unauthorized", "tailgat", "gate", "barrier", "access"),
        "Unauthorized access & gate issues",
    ),
    (("noise", "music", "disturb", "quiet"), "Noise & disturbance complaints"),
    (("delivery", "rider", "parcel", "vendor"), "Delivery & vendor disputes"),
    (("theft", "bike", "stolen", "vehicle"), "Theft & suspicious property"),
    (("fire", "smoke", "alarm"), "Fire safety & smoke alarms"),
    (
        ("pool", "chlorine", "chemical", "smell"),
        "Facilities & chemical odours",
    ),
    (
        ("elevator", "lift", "maintenance", "light", "fence"),
        "Maintenance & infrastructure",
    ),
    (
        ("dispute", "argument", "harass", "resident"),
        "Resident disputes & conduct",
    ),
    (("medical", "slip", "injur", "ambulance"), "Medical & injury incidents"),
    (
        ("drone", "suspicious", "unknown"),
        "Suspicious activity & unknown persons",
    ),
    (("security", "guard", "patrol"), "Security operations & staffing"),
]


def _distinct_keywords(terms: list[str], *, limit: int = 5) -> list[str]:
    """Drop redundant n-grams (e.g. keep ``hours security`` but not lone ``hours``)."""
    ordered = list(terms)
    selected: list[str] = []
    skipped_phrases: list[str] = []
    for term in ordered:
        if not term:
            continue
        dominated = False
        for kept in selected:
            if term == kept:
                dominated = True
                break
            if term in kept:
                dominated = True
                break
            if kept in term:
                dominated = True
                break
        if not dominated:
            words = term.split()
            for phrase in skipped_phrases:
                if len(words) == 1 and words[0] in phrase.split():
                    dominated = True
                    break
        if dominated:
            if " " in term:
                skipped_phrases.append(term)
            continue
        selected.append(term)
        if len(selected) >= limit:
            break
    return selected


def _friendly_theme_name(keywords: list[str]) -> str:
    blob = " ".join(keywords).lower()
    for fragments, name in _THEME_RULES:
        if any(frag in blob for frag in fragments):
            return name
    if keywords:
        return keywords[0].replace("_", " ").title() + "-related incidents"
    return "General incidents"


def _example_incidents(
    indices: list[int],
    records: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, str | None]]:
    examples: list[dict[str, str | None]] = []
    for i in indices[:limit]:
        row = records[i]
        title = str(row.get("title") or "").strip() or None
        narrative = str(row.get("narrative") or "").strip()
        snippet = narrative[:160] + ("…" if len(narrative) > 160 else "")
        examples.append(
            {
                "title": title,
                "narrative_snippet": snippet or None,
            }
        )
    return examples


def _timeline_sentence(temporal: dict[str, Any], n_docs: int) -> str:
    parts: list[str] = []
    wv = temporal.get("weekend_vs_weekday") or {}
    weekend = int(wv.get("weekend", 0))
    weekday = int(wv.get("weekday", 0))
    if weekend or weekday:
        total = weekend + weekday
        pct_wd = round(100 * weekday / total) if total else 0
        parts.append(f"{pct_wd}% on weekdays")

    hours = temporal.get("hour_bucket") or {}
    if hours:
        top_period = max(hours.items(), key=lambda x: x[1])[0]
        parts.append(f"most reports in the {top_period}")

    by_week = temporal.get("by_topic_week") or []
    if by_week:
        weeks = sorted({row["week"] for row in by_week})
        if len(weeks) >= 2:
            parts.append(f"activity from {weeks[0]} to {weeks[-1]}")

    if not parts:
        return (
            f"{n_docs} incidents in the selected window (no timing breakdown)."
        )
    return "; ".join(parts).capitalize() + "."


def enrich_topics_for_display(
    records: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    *,
    n_docs: int,
) -> list[dict[str, Any]]:
    """Add display names, share %, keywords, and example incidents to each topic."""
    id_to_index = {
        str(r.get("id")): i for i, r in enumerate(records) if r.get("id")
    }
    by_topic: dict[int, list[int]] = {}
    for assign in assignments:
        tid = int(assign["topic_id"])
        iid = assign.get("incident_id")
        if iid and str(iid) in id_to_index:
            by_topic.setdefault(tid, []).append(id_to_index[str(iid)])

    enriched: list[dict[str, Any]] = []
    for topic in topics:
        tid = int(topic["topic_id"])
        indices = by_topic.get(tid, [])
        raw_terms = [tw["term"] for tw in topic.get("top_terms", [])]
        keywords = _distinct_keywords(raw_terms)
        count = int(topic.get("document_count") or len(indices))
        share = round(100.0 * count / n_docs, 1) if n_docs else 0.0
        display_name = _friendly_theme_name(keywords)
        enriched.append(
            {
                **topic,
                "display_name": display_name,
                "keywords": keywords,
                "share_percent": share,
                "example_incidents": _example_incidents(indices, records),
            }
        )
    return sorted(enriched, key=lambda t: -float(t.get("share_percent", 0)))


def format_topic_report_text(
    *,
    record_count: int,
    documents_modelled: int,
    n_topics: int,
    topics: list[dict[str, Any]],
    timeline: str,
    note: str | None = None,
) -> str:
    """Plain-text report suitable for terminals and logs."""
    lines: list[str] = [
        "=" * 60,
        "INCIDENT THEME REPORT",
        "=" * 60,
        f"Reports analysed: {record_count} ({documents_modelled} with text)",
        f"Themes discovered: {n_topics}",
        "",
    ]
    if note:
        lines.extend([f"Note: {note}", ""])

    for i, topic in enumerate(topics, start=1):
        name = topic.get("display_name") or topic.get("label") or f"Theme {i}"
        share = topic.get("share_percent", 0)
        count = topic.get("document_count", 0)
        keywords = topic.get("keywords") or []
        kw = ", ".join(keywords) if keywords else "(none)"
        lines.extend(
            [
                f"── Theme {i}: {name}",
                f"   {count} incidents ({share}% of cohort)",
                f"   Keywords: {kw}",
            ]
        )
        for ex in topic.get("example_incidents") or []:
            title = ex.get("title")
            snippet = ex.get("narrative_snippet")
            if title:
                lines.append(f"   • {title}")
            elif snippet:
                lines.append(f"   • {snippet}")
        lines.append("")

    lines.extend(["── Timing", f"   {timeline}", "=" * 60])
    return "\n".join(lines)


def build_human_topic_report(
    *,
    records: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    temporal_overview: dict[str, Any],
    record_count: int,
    documents_modelled: int,
    n_topics: int,
    note: str | None = None,
) -> dict[str, Any]:
    """Structured + printable human-readable topic summary."""
    n_docs = documents_modelled or len(records)
    enriched = enrich_topics_for_display(
        records, topics, assignments, n_docs=n_docs
    )
    timeline = _timeline_sentence(temporal_overview, n_docs)
    full_text = format_topic_report_text(
        record_count=record_count,
        documents_modelled=documents_modelled,
        n_topics=n_topics,
        topics=enriched,
        timeline=timeline,
        note=note,
    )
    themes = [
        {
            "topic_id": t["topic_id"],
            "name": t.get("display_name"),
            "incident_count": t.get("document_count"),
            "share_percent": t.get("share_percent"),
            "keywords": t.get("keywords"),
            "examples": t.get("example_incidents"),
        }
        for t in enriched
    ]
    return {
        "headline": (
            f"{record_count} incident reports · {n_topics} recurring themes"
        ),
        "themes": themes,
        "timeline_summary": timeline,
        "full_text": full_text,
    }
