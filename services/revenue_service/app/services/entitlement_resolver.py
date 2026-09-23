"""Resolve effective entitlements for an estate subscription."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from app.core.config import settings

# Billing statuses that may still carry paid entitlements until period_end.
PAID_ACCESS_STATUSES = frozenset(
    {"active", "trialing", "cancelled", "past_due"}
)
# Narrow set used by some callers that only want "healthy" billing rows.
ACTIVE_STATUSES = frozenset({"active", "trialing"})
# Statuses that receive a grace-period extension before falling back to Access.
_GRACE_STATUSES = frozenset({"active", "trialing"})


def _access_entitlements(
    access_tier: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    Return Access-tier entitlements for fallback resolution.

    Args:
        access_tier: Seeded Access tier row, or None if not loaded.

    Returns:
        Entitlements map from the Access tier.

    Raises:
        ValueError: If access_tier is missing when fallback is required.
    """
    if not access_tier:
        raise ValueError(
            "access_tier is required when falling back to Access entitlements"
        )
    return dict(access_tier.get("entitlements") or {})


def period_still_valid(
    subscription: Mapping[str, Any], grace_days: int = 0
) -> bool:
    """Return True when period_end (extended by grace_days) is in the future."""
    raw = subscription.get("period_end")
    if not raw:
        return True
    try:
        end = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return True
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end + timedelta(days=max(0, grace_days)) > datetime.now(
        tz=timezone.utc
    )


def uses_access_fallback(
    subscription: Mapping[str, Any] | None,
    tier: Mapping[str, Any] | None,
) -> bool:
    """
    Return True when effective entitlements should come from the Access tier.

    Happens when there is no subscription, status is outside the paid-access
    set, the billing period has ended, or the tier row is missing.

    ``active``/``trialing`` subscriptions retain paid entitlements through
    ``period_end + RENEWAL_GRACE_PERIOD_DAYS`` so estates keep access while
    Paystack retries payment — matching the same grace logic used for AI
    grants. ``cancelled`` and ``past_due`` receive no grace (access runs to
    period_end exactly).
    """
    if not subscription:
        return True
    status = (subscription.get("status") or "").lower()
    if status not in PAID_ACCESS_STATUSES:
        return True
    grace = (
        settings.RENEWAL_GRACE_PERIOD_DAYS if status in _GRACE_STATUSES else 0
    )
    if not period_still_valid(subscription, grace_days=grace):
        return True
    if not tier:
        return True
    return False


def resolve_entitlements(
    *,
    subscription: Mapping[str, Any] | None,
    tier: Mapping[str, Any] | None,
    access_tier: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolve effective entitlements using plan precedence:

    1. If no subscription, status not in paid-access set, or period ended
       → access tier.
    2. If tier is_custom → estate_subscription.entitlements snapshot.
    3. Else → subscription_tier.entitlements.

    ``cancelled`` and ``past_due`` keep paid entitlements until ``period_end``
    (cancel turns off auto-renew but does not cut access early).

    Args:
        subscription: Active estate subscription row, or None.
        tier: Subscription tier row for the subscription, or None.
        access_tier: Seeded Access tier used as the free fallback.
            Required only when falling back; may be omitted for paid paths.

    Returns:
        Effective entitlements map for the estate.

    Raises:
        ValueError: If fallback is needed but access_tier was not provided.
    """
    if uses_access_fallback(subscription, tier):
        return _access_entitlements(access_tier)

    if tier.get("is_custom"):
        snapshot = subscription.get("entitlements")
        return dict(snapshot or {})

    return dict(tier.get("entitlements") or {})


def check_service_entitlement(
    entitlements: Mapping[str, Any],
    service_key: str,
    limit_type: str | None = None,
) -> dict[str, Any]:
    """
    Evaluate whether a service_key is allowed given entitlements.

    Args:
        entitlements: Effective entitlements map.
        service_key: Catalog service key to evaluate.
        limit_type: Optional catalog limit_type hint
            (boolean | int | count | duration_days).

    Returns:
        Dict with allowed, limit, and limit_type.
    """
    value = entitlements.get(service_key)
    if limit_type == "boolean" or isinstance(value, bool):
        allowed = bool(value) if value is not None else False
        return {
            "allowed": allowed,
            "limit": allowed,
            "limit_type": limit_type or "boolean",
        }
    if limit_type in ("int", "count", "duration_days") or isinstance(
        value, int
    ):
        limit = int(value) if value is not None else 0
        return {
            "allowed": limit > 0,
            "limit": limit,
            "limit_type": limit_type
            or ("int" if not isinstance(value, bool) else "boolean"),
        }
    # Absent key
    if limit_type == "boolean":
        return {"allowed": False, "limit": False, "limit_type": "boolean"}
    if limit_type in ("int", "count", "duration_days"):
        return {"allowed": False, "limit": 0, "limit_type": limit_type}
    return {"allowed": False, "limit": None, "limit_type": limit_type}
