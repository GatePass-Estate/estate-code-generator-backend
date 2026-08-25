"""Sync tier-bundled AI grants onto estate_ai_feature rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.repositories.db_revenue import DbRevenueRepository

logger = logging.getLogger(__name__)

_GRANT_ROLLBACK_FIELDS = (
    "estate_subscription_id",
    "source",
    "status",
    "expires_at",
)


@dataclass
class GrantSyncRollback:
    """Tracks grant writes so partial sync failures can be reversed."""

    estate_id: str
    subscription_id: str
    operation: str
    created_grant_ids: list[str] = field(default_factory=list)
    updated_grants: dict[str, dict[str, Any]] = field(default_factory=dict)

    def record_create(self, grant_id: str) -> None:
        self.created_grant_ids.append(grant_id)

    def record_update(self, grant: dict[str, Any]) -> None:
        grant_id = str(grant["id"])
        if grant_id in self.updated_grants:
            return
        self.updated_grants[grant_id] = {
            key: grant.get(key) for key in _GRANT_ROLLBACK_FIELDS
        }

    def touched_ids(self) -> dict[str, list[str]]:
        return {
            "created_grant_ids": list(self.created_grant_ids),
            "updated_grant_ids": list(self.updated_grants.keys()),
        }

    async def apply(self, repo: DbRevenueRepository) -> None:
        """Best-effort undo of grant rows touched during a failed sync."""
        logger.warning(
            "Rolling back AI grant sync operation=%s estate_id=%s "
            "subscription_id=%s created_grant_ids=%s updated_grant_ids=%s",
            self.operation,
            self.estate_id,
            self.subscription_id,
            self.created_grant_ids,
            list(self.updated_grants.keys()),
        )
        for grant_id, snapshot in self.updated_grants.items():
            try:
                await repo.update_estate_ai_feature(grant_id, snapshot)
                logger.info(
                    "Rolled back estate_ai_feature update grant_id=%s "
                    "estate_id=%s subscription_id=%s operation=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                )
            except Exception:
                logger.exception(
                    "Failed to rollback estate_ai_feature update "
                    "grant_id=%s estate_id=%s subscription_id=%s "
                    "operation=%s prior_snapshot=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                    snapshot,
                )
        for grant_id in reversed(self.created_grant_ids):
            try:
                await repo.delete_estate_ai_feature(grant_id)
                logger.info(
                    "Rolled back estate_ai_feature create grant_id=%s "
                    "estate_id=%s subscription_id=%s operation=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                )
            except Exception:
                logger.exception(
                    "Failed to rollback estate_ai_feature create "
                    "grant_id=%s estate_id=%s subscription_id=%s "
                    "operation=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                )


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

    Idempotent: safe to retry with the same inputs after a partial failure.
    Rolls back grant rows created/updated in this call if a later write fails.
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
    tier_id = str(tier.get("id") or "")
    rollback = GrantSyncRollback(
        estate_id=estate_id,
        subscription_id=subscription_id,
        operation="sync_tier_ai_grants",
    )

    try:
        for feature_key in keys:
            feature = catalog.get(feature_key)
            if not feature:
                logger.warning(
                    "Skipping unknown AI feature_key=%s estate_id=%s "
                    "subscription_id=%s tier_id=%s",
                    feature_key,
                    estate_id,
                    subscription_id,
                    tier_id,
                )
                continue
            feature_id = str(feature["id"])
            is_free = bool(feature.get("is_free"))
            grant = by_feature_id.get(feature_id)
            if grant:
                rollback.record_update(grant)
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
                created = await repo.create_estate_ai_feature(payload)
                rollback.record_create(str(created["id"]))
    except Exception:
        logger.exception(
            "AI grant sync failed estate_id=%s subscription_id=%s "
            "tier_id=%s feature_keys=%s touched=%s",
            estate_id,
            subscription_id,
            tier_id,
            keys,
            rollback.touched_ids(),
        )
        await rollback.apply(repo)
        raise


async def extend_subscription_ai_grants(
    repo: DbRevenueRepository,
    *,
    estate_id: str,
    subscription_id: str,
    new_period_end: datetime,
) -> None:
    """
    Extend expires_at for paid grants linked to this subscription.

    Idempotent: safe to retry with the same ``new_period_end``.
    Rolls back grant rows updated in this call if a later write fails.
    """
    grants = await repo.list_estate_ai_features(estate_id)
    end_iso = new_period_end.isoformat()
    rollback = GrantSyncRollback(
        estate_id=estate_id,
        subscription_id=subscription_id,
        operation="extend_subscription_ai_grants",
    )

    try:
        for grant in grants:
            if str(grant.get("estate_subscription_id") or "") != str(
                subscription_id
            ):
                continue
            if bool(grant.get("is_free")):
                continue
            rollback.record_update(grant)
            await repo.update_estate_ai_feature(
                str(grant["id"]), {"expires_at": end_iso, "status": "active"}
            )
    except Exception:
        logger.exception(
            "AI grant extend failed estate_id=%s subscription_id=%s "
            "new_period_end=%s touched=%s",
            estate_id,
            subscription_id,
            end_iso,
            rollback.touched_ids(),
        )
        await rollback.apply(repo)
        raise


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
