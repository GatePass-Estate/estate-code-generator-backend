"""Resolve effective entitlements for an estate subscription."""

from __future__ import annotations

from typing import Any, Mapping

ACTIVE_STATUSES = frozenset({"active", "trialing"})


def resolve_entitlements(
    *,
    subscription: Mapping[str, Any] | None,
    tier: Mapping[str, Any] | None,
    access_tier: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Resolve effective entitlements using plan precedence:

    1. If no subscription or status not in active/trialing → access tier.
    2. If tier is_custom → estate_subscription.entitlements snapshot.
    3. Else → subscription_tier.entitlements.

    Note: past_due is intentionally treated as inactive for entitlement
    resolution in Phase 1 (falls back to Access), matching the plan text
    that only active/trialing keep paid entitlements.

    Args:
        subscription: Active estate subscription row, or None.
        tier: Subscription tier row for the subscription, or None.
        access_tier: Seeded Access tier used as the free fallback.

    Returns:
        Effective entitlements map for the estate.
    """
    access_ents = dict(access_tier.get("entitlements") or {})

    if not subscription:
        return access_ents

    status = (subscription.get("status") or "").lower()
    if status not in ACTIVE_STATUSES:
        return access_ents

    if not tier:
        return access_ents

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
