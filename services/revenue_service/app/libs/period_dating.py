"""Period dating helpers for subscribe / renew / cancel."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_period_end(
    *,
    paid_at: datetime,
    duration: timedelta,
    old_period_end: datetime | None,
    grace_days: int,
) -> datetime:
    """
    Resolve the next period_end using plan dating rules.

    - First subscribe (no old_period_end): paid_at + duration
    - Manual/auto renew while paid_at is within grace after old_end:
      old_end + duration
    - Manual renew after grace: paid_at + duration
    """
    paid = _as_utc(paid_at)
    if old_period_end is None:
        return paid + duration

    old_end = _as_utc(old_period_end)
    grace_end = old_end + timedelta(days=max(0, grace_days))
    if paid <= grace_end:
        return old_end + duration
    return paid + duration
