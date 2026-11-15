"""Cleaning and normalization using pandas on log-derived rows."""

from typing import Any

import pandas as pd
from pandas.api.types import is_object_dtype, is_string_dtype


def _is_null_or_empty(value: Any) -> bool:
    """True if the value should be dropped from a cleaned record."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


async def wrangle_visit_records(
    raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Normalize log rows in a DataFrame and drop null / empty fields per record.

    Empty strings are treated as missing. Whitespace-only strings are treated
    as empty. Rows with no non-empty fields become ``{}``.
    """
    if not raw:
        return []

    df = pd.DataFrame(raw)
    df = df.replace("", pd.NA)

    for col in df.columns:
        series = df[col]
        if not (is_object_dtype(series) or is_string_dtype(series)):
            continue
        mask = series.map(
            lambda x: isinstance(x, str) and x.strip() == ""
            if isinstance(x, str)
            else False
        )
        df.loc[mask, col] = pd.NA

    cleaned: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rec = {k: v for k, v in row.items() if not _is_null_or_empty(v)}
        cleaned.append(rec)

    return cleaned
