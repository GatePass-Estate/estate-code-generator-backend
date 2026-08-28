"""Period dating helpers for subscribe / renew / cancel."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_utc_datetime(raw: Any) -> datetime | None:
    """Parse an ISO timestamp to UTC, or return None if missing/invalid."""
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    return _as_utc(parsed)


def paid_feature_access_valid(
    *,
    status: str,
    expires_at: Any,
    grace_days: int,
    now: datetime | None = None,
) -> bool:
    """
    Whether a paid AI grant is still usable for access checks.

    - ``active``: allowed through ``expires_at + grace_days`` so renewals can
      retry before the cron marks the grant expired.
    - ``cancelled`` / ``past_due`` / other non-expired statuses: allowed only
      until ``expires_at`` (no grace).
    - Missing/unparseable ``expires_at``: treated as still valid.
    """
    exp = _parse_utc_datetime(expires_at)
    if exp is None:
        return True

    current = _as_utc(now or datetime.now(tz=timezone.utc))
    normalized = (status or "").lower()
    if normalized == "active":
        return exp + timedelta(days=max(0, grace_days)) > current
    return exp > current


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
