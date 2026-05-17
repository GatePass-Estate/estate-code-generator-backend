"""Tests for TF-IDF + NMF incident topic discovery."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.pipeline.incident_topic_modelling import discover_incident_topics


def _row(
    *,
    narrative: str,
    title: str | None = None,
    category: list[str] | None = None,
    custom_category: str | None = None,
    occurred_at: datetime | None = None,
) -> dict:
    return {
        "id": str(uuid4()),
        "title": title,
        "category": category or [],
        "custom_category": custom_category,
        "narrative": narrative,
        "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
    }


def test_discover_topics_returns_multiple_topics_for_diverse_corpus():
    records = [
        _row(
            title="Gate tailgating",
            category=["unauthorized_access"],
            narrative="Unknown vehicle followed resident through main gate.",
        ),
        _row(
            title="Delivery dispute",
            category=["dispute"],
            narrative="Rider argued with security at reception over parcel.",
        ),
        _row(
            title="Night noise",
            category=["noise_disturbance"],
            narrative="Loud music reported from block C after midnight.",
        ),
        _row(
            title="Broken fence light",
            category=["maintenance", "security"],
            narrative="Perimeter lighting out near east fence.",
        ),
        _row(
            title="Suspicious bike",
            category=["security", "theft"],
            narrative="Untagged bicycle left at visitor parking overnight.",
        ),
        _row(
            title="Pool chemical smell",
            category=[],
            custom_category="facilities",
            narrative="Strong chlorine odor near plant room.",
        ),
    ]
    out = discover_incident_topics(records, n_topics=3)
    assert out["method"] == "tfidf_nmf"
    assert out["n_topics"] == 3
    assert len(out["topics"]) == 3
    assert len(out["assignments"]) == len(records)
    assert out["temporal_overview"].get("hour_bucket")
    assert out.get("report_text")
    assert out["human_report"]["themes"]
    assert out["topics"][0].get("display_name")


def test_too_few_records_returns_note_without_topics():
    records = [
        _row(narrative="Single incident only."),
        _row(narrative="Another short row."),
    ]
    out = discover_incident_topics(records)
    assert out["n_topics"] == 0
    assert out["topics"] == []
    assert "at least" in (out.get("note") or "").lower()
