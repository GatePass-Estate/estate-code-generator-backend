"""Sync tier-bundled AI grants onto estate_ai_feature rows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.repositories.db_revenue import DbRevenueRepository

logger = logging.getLogger(__name__)


async def sync_tier_ai_grants(
    repo: DbRevenueRepository,
    *,
    estate_id: str,
    subscription_id: str,
    tier: dict[str, Any],
    period_end: datetime,
    extra_feature_keys: list[str] | None = None,
) -> None:
    """
    Upsert estate_ai_feature rows for tier.included_ai_features (+ extras).

    Existing grants keep ``is_installed``. New grants are installed.
    Paid grants get ``expires_at=period_end``.
    """
    catalog = await repo.get_ai_feature_map()
    existing = await repo.list_estate_ai_features(estate_id)
    by_feature_id = {str(g.get("ai_feature_id")): g for g in existing}

    keys = list(tier.get("included_ai_features") or [])
    for key in extra_feature_keys or []:
        if key not in keys:
            keys.append(key)

    now = datetime.now(tz=timezone.utc)
    period_end_iso = period_end.isoformat()

    for feature_key in keys:
        feature = catalog.get(feature_key)
        if not feature:
            logger.warning(
                "Skipping unknown AI feature_key=%s for estate_id=%s",
                feature_key,
                estate_id,
            )
            continue
        feature_id = str(feature["id"])
        is_free = bool(feature.get("is_free"))
        grant = by_feature_id.get(feature_id)
        if grant:
            patch: dict[str, Any] = {
                "estate_subscription_id": subscription_id,
                "source": "subscription_tier",
                "status": "active",
            }
            if not is_free:
                patch["expires_at"] = period_end_iso
            await repo.update_estate_ai_feature(str(grant["id"]), patch)
        else:
            payload: dict[str, Any] = {
                "estate_id": estate_id,
                "ai_feature_id": feature_id,
                "source": "subscription_tier",
                "estate_subscription_id": subscription_id,
                "is_installed": True,
                "status": "active",
                "is_free": is_free,
                "auto_renew": True,
                "starts_at": now.isoformat(),
            }
            if not is_free:
                payload["expires_at"] = period_end_iso
            await repo.create_estate_ai_feature(payload)


async def extend_subscription_ai_grants(
    repo: DbRevenueRepository,
    *,
    estate_id: str,
    subscription_id: str,
    new_period_end: datetime,
) -> None:
    """Extend expires_at for paid grants linked to this subscription."""
    grants = await repo.list_estate_ai_features(estate_id)
    end_iso = new_period_end.isoformat()
    for grant in grants:
        if str(grant.get("estate_subscription_id") or "") != str(
            subscription_id
        ):
            continue
        if bool(grant.get("is_free")):
            continue
        await repo.update_estate_ai_feature(
            str(grant["id"]), {"expires_at": end_iso, "status": "active"}
        )


async def provision_standalone_ai_grant(
    repo: DbRevenueRepository,
    *,
    estate_id: str,
    feature: dict[str, Any],
    period_end: datetime,
    existing_grant: dict[str, Any] | None = None,
) -> dict:
    """
    Create/update a standalone paid AI grant (checkout without Paystack).

    Callers that already loaded the catalog row and estate grants should pass
    ``feature`` and ``existing_grant`` to avoid duplicate db-service reads.
    """
    feature_id = str(feature["id"])
    is_free = bool(feature.get("is_free"))
    grant = existing_grant
    now = datetime.now(tz=timezone.utc)
    payload: dict = {
        "source": "standalone_purchase",
        "is_installed": True,
        "status": "active",
        "is_free": is_free,
        "auto_renew": True,
        "starts_at": now.isoformat(),
    }
    if not is_free:
        payload["expires_at"] = period_end.isoformat()

    if grant:
        # Keep the later expires_at when re-purchasing.
        if not is_free and grant.get("expires_at"):
            try:
                old = datetime.fromisoformat(
                    str(grant["expires_at"]).replace("Z", "+00:00")
                )
                if old > period_end:
                    payload["expires_at"] = old.isoformat()
            except Exception:
                pass
        result = await repo.update_estate_ai_feature(str(grant["id"]), payload)
    else:
        result = await repo.create_estate_ai_feature(
            {
                "estate_id": estate_id,
                "ai_feature_id": feature_id,
                **payload,
            }
        )
    return result
