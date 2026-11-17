"""Validity evaluation for visitor access codes stored in Redis."""

from __future__ import annotations

from datetime import datetime, time, timezone


DATETIME_FMT = "%Y-%m-%d %H:%M:%S.%f%z"


def parse_datetime(value: str) -> datetime:
    """Parse a cached UTC datetime string."""
    return datetime.strptime(value, DATETIME_FMT)


def parse_time_of_day(value: str) -> time:
    """Parse a daily window bound such as ``09:00`` or ``17:30:00``."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time-of-day: {value}")


def _get_validity_period(record: dict) -> dict:
    period = record.get("validity_period")
    if isinstance(period, dict):
        return period
    return {}


def _get_period_start(record: dict) -> datetime | None:
    start = _get_validity_period(record).get("start")
    if start:
        return parse_datetime(start)
    return None


def _get_period_end(record: dict) -> datetime | None:
    period = _get_validity_period(record)
    end = period.get("end")
    if end:
        return parse_datetime(end)
    valid_until = record.get("valid_until")
    if valid_until:
        return parse_datetime(valid_until)
    return None


def _is_within_daily_window(now: datetime, window: dict) -> bool:
    """
    Return whether ``now`` falls inside the configured daily window.

    If either bound is missing, the window is treated as unrestricted.
    """
    window_start = window.get("start")
    window_end = window.get("end")
    if not window_start or not window_end:
        return True

    current_time = now.time()
    daily_start = parse_time_of_day(window_start)
    daily_end = parse_time_of_day(window_end)
    if daily_start <= daily_end:
        return daily_start <= current_time <= daily_end
    return current_time >= daily_start or current_time <= daily_end


def evaluate_code_validity(record: dict, now: datetime | None = None) -> dict:
    """
    Enrich a cached visitor code with computed validity flags.

    ``is_valid`` is False when any of the following are true:
    - current time is before ``validity_period.start``
    - current time is after ``validity_period.end`` / ``valid_until``
    - ``frozen`` is True
    - current UTC time-of-day is outside ``validity_window``

    Also adds diagnostic flags: ``is_before_period_start``,
    ``is_outside_daily_window``, and ``is_frozen``.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    period_start = _get_period_start(record)
    period_end = _get_period_end(record)

    is_before_period_start = period_start is not None and now < period_start
    is_expired = period_end is not None and now > period_end
    is_frozen = bool(record.get("frozen", False))

    validity_window = record.get("validity_window")
    if not isinstance(validity_window, dict):
        validity_window = {}
    is_outside_daily_window = not _is_within_daily_window(now, validity_window)

    is_valid = not (
        is_before_period_start
        or is_expired
        or is_frozen
        or is_outside_daily_window
    )

    result = dict(record)
    result["is_expired"] = is_expired
    result["is_before_period_start"] = is_before_period_start
    result["is_frozen"] = is_frozen
    result["is_outside_daily_window"] = is_outside_daily_window
    result["is_valid"] = is_valid
    return result
