"""Tests for human-readable topic report formatting."""

from app.pipeline.incident_topic_human_report import (
    _distinct_keywords,
    _friendly_theme_name,
)


def test_distinct_keywords_drops_redundant_ngrams():
    raw = ["residents", "security", "hours security", "hours", "unknown"]
    assert _distinct_keywords(raw) == ["residents", "security", "unknown"]


def test_friendly_theme_name_maps_security_terms():
    name = _friendly_theme_name(["unauthorized", "gate", "security", "access"])
    assert "Unauthorized access" in name
