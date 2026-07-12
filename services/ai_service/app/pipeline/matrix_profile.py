"""
Matrix Profile helpers for temporal (time-series) anomaly detection.

Builds a **daily** visit-count series from an estate's log rows, computes the
z-normalized Matrix Profile with ``stumpy.stump`` (see Yeh et al., 2016), and
scores the **latest subsequence** (the most recent one-week window) as a
*discord* (largest nearest-neighbour distance). Higher score => the latest week
looks more unlike the rest of the estate's history.

Reference: https://medium.com/@pw33392/using-the-matrix-profile-to-detect-anomalies-in-time-series-bca14883e0fb
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import stumpy

#: Library fallback subsequence length in days when a caller omits ``m``. The
#: runtime value is ``settings.TEMPORAL_SUBSEQUENCE_WINDOW_DAYS`` (see the
#: temporal orchestrator), which is what the API path actually uses.
DEFAULT_WINDOW_DAYS = 7


@dataclass(frozen=True)
class MatrixProfileScore:
    """Latest-subsequence discord score plus transparency fields."""

    score: float
    window_size: int
    series_length: int
    latest_window_index: int
    latest_profile_value: float
    profile_mean: float
    profile_max: float
    discord_index: int
    computed: bool
    note: str | None = None


def parse_event_time(rec: dict[str, Any]) -> datetime | None:
    """Parse a log row's primary event time (visit/access/created) to UTC."""
    for key in ("visit_time", "access_time", "created_at"):
        raw = rec.get(key)
        if raw is None:
            continue
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        if isinstance(raw, str):
            v = raw.replace("Z", "+00:00")
            try:
                ts = datetime.fromisoformat(v)
            except ValueError:
                continue
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return None


def build_daily_count_series(
    rows: list[dict[str, Any]],
    from_dt: datetime,
    to_dt: datetime,
) -> np.ndarray:
    """
    Bin log rows into a visits-per-day series over ``[from_dt, to_dt]``.

    One bucket per calendar day (UTC). Rows without a parseable event time or
    outside the span are ignored. Returns a 1D ``float64`` array of counts whose
    length is the number of days spanned (inclusive).
    """
    from_day = from_dt.date()
    n_days = max(1, (to_dt.date() - from_day).days + 1)
    counts = np.zeros(n_days, dtype=np.float64)
    for r in rows:
        ts = parse_event_time(r)
        if ts is None:
            continue
        idx = (ts.date() - from_day).days
        if 0 <= idx < n_days:
            counts[idx] += 1.0
    return counts


def compute_matrix_profile(series: np.ndarray, m: int) -> np.ndarray:
    """
    Matrix profile (nearest-neighbour z-normalized distances) via stumpy.

    ``stumpy.stump`` returns an ``(n - m + 1, 4)`` array; column 0 is the
    matrix profile ``P`` (the article's ``.P_``). Non-finite entries are set to
    ``0.0`` so downstream scoring stays numerically stable.
    """
    series = np.ascontiguousarray(series, dtype=np.float64)
    mp = stumpy.stump(series, m=m)
    profile = np.asarray(mp[:, 0], dtype=np.float64)
    profile[~np.isfinite(profile)] = 0.0
    return profile


def score_latest_subsequence(
    series: np.ndarray,
    m: int = DEFAULT_WINDOW_DAYS,
) -> MatrixProfileScore:
    """
    Score the most recent length-``m`` subsequence of ``series`` as a discord.

    The latest window starts at ``len(series) - m``. Its score is the percentile
    rank of that window's matrix-profile value among all windows, so ``1.0``
    means the latest week is the strongest discord (most unusual) in the history.

    Callers must ensure the series is long enough before calling (see the
    orchestrator's history-length check, driven by
    ``settings.TEMPORAL_MIN_HISTORY_WINDOW_MULTIPLE``). If the series is long
    enough but too flat (fewer than two non-empty days) the result is
    ``computed=False`` with ``score=0.0``.
    """
    n = int(series.shape[0])
    if int(np.count_nonzero(series)) < 2:
        return MatrixProfileScore(
            score=0.0,
            window_size=m,
            series_length=n,
            latest_window_index=-1,
            latest_profile_value=0.0,
            profile_mean=0.0,
            profile_max=0.0,
            discord_index=-1,
            computed=False,
            note="series has fewer than two non-empty days",
        )

    profile = compute_matrix_profile(series, m)
    latest_start = profile.shape[0] - 1
    latest_value = float(profile[latest_start])

    # Fraction of windows strictly *less* unusual than the latest one. Strict
    # ``<`` keeps a typical/minimum window near 0 even when many windows tie
    # (e.g. a perfectly periodic series where every profile value is ~0).
    rank = float(np.mean(profile < latest_value))
    return MatrixProfileScore(
        score=float(np.clip(rank, 0.0, 1.0)),
        window_size=m,
        series_length=n,
        latest_window_index=latest_start,
        latest_profile_value=latest_value,
        profile_mean=float(np.mean(profile)),
        profile_max=float(np.max(profile)),
        discord_index=int(np.argmax(profile)),
        computed=True,
        note=None,
    )
