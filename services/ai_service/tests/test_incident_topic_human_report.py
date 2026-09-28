"""Tests for human-readable topic report formatting."""

from app.pipeline.incident_topic_human_report import (
    _build_executive_summary,
    _distinct_keywords,
    _friendly_theme_name,
    build_human_topic_report,
    format_topic_report_text,
)


def test_distinct_keywords_drops_redundant_ngrams():
    raw = ["residents", "security", "hours security", "hours", "unknown"]
    assert _distinct_keywords(raw) == ["residents", "security", "unknown"]


def test_friendly_theme_name_maps_security_terms():
    name = _friendly_theme_name(["unauthorized", "gate", "security", "access"])
    assert "Unauthorized access" in name


def test_executive_summary_at_least_twenty_words():
    text = _build_executive_summary(
        record_count=12,
        n_topics=2,
        topics=[
            {
                "display_name": "Unauthorized access & gate issues",
                "share_percent": 58.3,
            },
            {
                "display_name": "Delivery & vendor disputes",
                "share_percent": 41.7,
            },
        ],
        timeline="67% on weekdays; most reports in the morning.",
    )
    assert len(text.split()) >= 20
    assert "12 incident reports" in text


def test_format_topic_report_text_has_no_markdown_decorations():
    body = format_topic_report_text(
        record_count=3,
        documents_modelled=3,
        n_topics=1,
        topics=[
            {
                "display_name": "Test theme",
                "share_percent": 100.0,
                "document_count": 3,
                "keywords": ["alpha"],
                "example_incidents": [{"title": "Example title"}],
            }
        ],
        timeline="Most reports in the morning.",
    )
    assert "====" not in body
    assert "──" not in body
    assert "•" not in body
    assert body.startswith("Incident theme report")


def test_build_human_topic_report_headline_matches_executive_length():
    report = build_human_topic_report(
        records=[{"id": "1", "title": "A", "narrative": "Noise complaint."}],
        topics=[
            {
                "topic_id": 0,
                "label": "noise",
                "top_terms": [{"term": "noise", "weight": 1.0}],
                "document_count": 1,
            }
        ],
        assignments=[{"incident_id": "1", "topic_id": 0, "weight": 1.0}],
        temporal_overview={"hour_bucket": {"morning": 1}},
        record_count=1,
        documents_modelled=1,
        n_topics=1,
    )
    assert len(report["headline"].split()) >= 20
    assert "====" not in report["full_text"]
