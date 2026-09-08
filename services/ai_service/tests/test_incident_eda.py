"""Category EDA ranking, peak-time buckets, and trend formatting."""

from app.pipeline.incident_eda import (
    build_category_eda,
    format_incident_trends,
)


def _row(category: str, hour: str, narrative: str, title: str | None = None):
    return {
        "category": [category],
        "custom_category": None,
        "title": title or category,
        "narrative": narrative,
        "occurred_at": f"2026-04-01T{hour}:00:00Z",
    }


def test_category_eda_splits_top_five_and_groups_the_rest():
    records = []
    counts = {
        "theft": 6,
        "security": 5,
        "noise_disturbance": 4,
        "maintenance": 3,
        "dispute": 2,
        "fire_safety": 1,
        "other": 1,
    }
    for label, n in counts.items():
        for i in range(n):
            records.append(_row(label, "10", f"{label} narrative {i}"))

    eda = build_category_eda(records)
    assert eda["top_1"]["category"] == "theft"
    assert eda["top_1"]["incident_count"] == 6
    assert eda["top_1"]["peak_time"] == "morning"
    assert eda["top_5"]["category"] == "dispute"
    other = eda["other_categories"]
    assert list(other) == ["fire_safety", "other"]
    assert other["fire_safety"]["incident_count"] == 1
    assert len(eda["top_1"]["sample_reports"]) == 2


def test_peak_time_uses_dominant_occurred_at_bucket():
    records = [
        _row("theft", "08", "morning one"),
        _row("theft", "09", "morning two"),
        _row("theft", "21", "night one"),
    ]
    eda = build_category_eda(records)
    assert eda["top_1"]["peak_time"] == "morning"
    assert eda["top_1"]["percentage_share"] == 100.0


def test_category_eda_ignores_custom_category_labels():
    records = [
        _row("theft", "08", "Gate forced"),
        {
            "category": [],
            "custom_category": "drone over gardens",
            "title": "Drone",
            "narrative": "Hobby drone hovering over block C.",
            "occurred_at": "2026-04-01T21:00:00Z",
        },
        {
            "category": ["not_a_real_category"],
            "custom_category": "pool chemicals",
            "title": "Chemicals",
            "narrative": "Strong chlorine smell at the pool.",
            "occurred_at": "2026-04-01T15:00:00Z",
        },
    ]
    eda = build_category_eda(records)
    assert eda["top_1"]["category"] == "theft"
    assert eda["top_1"]["incident_count"] == 1
    assert eda["top_2"] is None
    assert eda["other_categories"] == {}


def test_format_trends_uses_top_category_and_missing_count():
    eda = build_category_eda(
        [
            _row("theft", "20", "Gate forced"),
            _row("theft", "21", "Second theft"),
            {
                "category": [],
                "custom_category": None,
                "title": "Blank",
                "narrative": "No label",
                "occurred_at": "2026-04-01T12:00:00Z",
            },
        ]
    )
    text = format_incident_trends(
        record_count=3,
        category_eda=eda,
        stats={"rows_without_category": 1},
    )
    assert "3 incident reports" in text
    assert "theft is the most frequent" in text
    assert "evening/night" in text
    assert "1 report has no taxonomy category" in text
