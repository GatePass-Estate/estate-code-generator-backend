"""Resolve effective entitlements for an estate subscription."""

from __future__ import annotations

from typing import Any, Mapping

ACTIVE_STATUSES = frozenset({"active", "trialing"})


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


def resolve_entitlements(
    *,
    subscription: Mapping[str, Any] | None,
    tier: Mapping[str, Any] | None,
    access_tier: Mapping[str, Any] | None = None,
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
            Required only when falling back; may be omitted for paid paths.

    Returns:
        Effective entitlements map for the estate.

    Raises:
        ValueError: If fallback is needed but access_tier was not provided.
    """
    if not subscription:
        return _access_entitlements(access_tier)

    status = (subscription.get("status") or "").lower()
    if status not in ACTIVE_STATUSES:
        return _access_entitlements(access_tier)

    if not tier:
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
