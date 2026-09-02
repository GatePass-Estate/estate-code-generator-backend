"""Billing entitlement checks for estate AI grants.

Mirrors revenue-service ``check_ai_feature`` / ``paid_feature_access_valid``
so marketplace ``purchased`` means currently entitled, not merely that a
grant row exists.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

# Match revenue-service ``RENEWAL_GRACE_PERIOD_DAYS``.
_RENEWAL_GRACE_PERIOD_DAYS = 7


def _parse_utc(raw: Any) -> datetime | None:
    """Parse an ISO timestamp to UTC, or None if missing/invalid."""
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def grant_is_entitled(grant: dict | None) -> bool:
    """True if the grant currently entitles the estate to the feature.

    Free grants skip expiry. ``expired`` is never entitled. ``active`` stays
    valid through ``expires_at`` plus a renewal grace window. ``cancelled``
    and ``past_due`` stay valid only until ``expires_at``. Install state is
    ignored: list ``purchased`` is billing entitlement, not ``is_installed``.
    """
    if not grant:
        return False
    if grant.get("is_free"):
        return True
    status = (grant.get("status") or "").lower()
    if status == "expired":
        return False
    expires_at = _parse_utc(grant.get("expires_at"))
    if expires_at is None:
        return True
    now = datetime.now(tz=timezone.utc)
    if status == "active":
        grace = timedelta(days=_RENEWAL_GRACE_PERIOD_DAYS)
        return expires_at + grace > now
    return expires_at > now


def is_purchased(feature_ids: list[str], grants: dict[str, dict]) -> bool:
    """True if the estate is currently entitled to any child feature."""
    return any(grant_is_entitled(grants.get(fid)) for fid in feature_ids)
