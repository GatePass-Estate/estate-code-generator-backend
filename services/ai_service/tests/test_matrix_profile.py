"""Tests for the Matrix Profile temporal-anomaly helpers."""

from datetime import datetime, timezone

import numpy as np

from app.pipeline.matrix_profile import (
    build_daily_count_series,
    compute_matrix_profile,
    score_latest_subsequence,
)

_UTC = timezone.utc


def test_matrix_profile_finds_injected_flat_region():
    """Article sanity check: a flat region in a sine wave is the discord."""
    x = np.sin(np.linspace(0, 20, 1000))
    x[500:550] = 0.0
    profile = compute_matrix_profile(x, m=150)
    discord = int(np.argmax(profile))
    # The window (length 150) with the largest nearest-neighbour distance
    # should overlap the injected flat region [500, 550).
    assert 350 <= discord <= 550


def test_build_daily_count_series_bins_by_day():
    from_dt = datetime(2026, 1, 1, 0, 0, tzinfo=_UTC)
    to_dt = datetime(2026, 1, 4, 23, 0, tzinfo=_UTC)
    rows = [
        {"visit_time": "2026-01-01T00:30:00Z"},
        {"visit_time": "2026-01-01T18:45:00Z"},
        {"visit_time": "2026-01-03T10:10:00Z"},
        {"visit_time": None},
        {"other": "no-timestamp"},
    ]
    series = build_daily_count_series(rows, from_dt, to_dt)
    assert series.shape[0] == 4  # Jan 1..4 inclusive
    assert series[0] == 2.0
    assert series[2] == 1.0
    assert series.sum() == 3.0


def test_score_latest_subsequence_flags_recent_anomaly():
    weekly = np.array([2.0, 3.0, 2.0, 4.0, 3.0, 8.0, 9.0])  # weekend peak
    series = np.tile(weekly, 12).astype(np.float64)  # 84 days
    # Make the most recent week an anomalous flat burst.
    series[-7:] = 40.0

    result = score_latest_subsequence(series, m=7)
    assert result.computed is True
    assert result.latest_window_index == series.shape[0] - 7
    assert result.score > 0.5


def test_score_latest_subsequence_typical_week_low_score():
    weekly = np.array([2.0, 3.0, 2.0, 4.0, 3.0, 8.0, 9.0])
    series = np.tile(weekly, 12).astype(np.float64)
    result = score_latest_subsequence(series, m=7)
    assert result.computed is True
    assert result.score < 0.9


def test_score_latest_subsequence_flat_series_not_computed():
    series = np.zeros(60, dtype=np.float64)
    series[3] = 1.0
    result = score_latest_subsequence(series, m=7)
    assert result.computed is False
    assert result.score == 0.0
