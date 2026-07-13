"""Build a zero-filled daily validation-count series for forecasting and temporal analysis."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

import pandas as pd


def _to_utc_naive_day(ts: datetime) -> pd.Timestamp:
    """Normalise to a tz-naive UTC day (floor to midnight)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return pd.Timestamp(ts).tz_localize(None).normalize()


def build_daily_series(
    timestamps: Iterable[datetime],
    start: datetime,
    end: datetime,
) -> pd.Series:
    """
    Count events per calendar day and reindex over the full ``[start, end]``
    daily range, filling days with no validations as ``0``.

    Used by ARIMA volume forecasting and temporal Matrix Profile analysis.
    Zero-filling matters because validation counts are sparse and gappy;
    downstream models need a regular, contiguous daily index.
    """
    start_day = _to_utc_naive_day(start)
    end_day = _to_utc_naive_day(end)
    full_index = pd.date_range(start=start_day, end=end_day, freq="D")

    days = [_to_utc_naive_day(ts) for ts in timestamps]
    if days:
        ones = pd.Series(1, index=pd.DatetimeIndex(days))
        counts = ones.groupby(level=0).sum()
    else:
        counts = pd.Series(dtype="int64")

    series = counts.reindex(full_index, fill_value=0).astype("float64")
    series.index.name = "date"
    series.name = "volume"
    return series
