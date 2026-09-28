"""Sync tier-bundled AI grants onto estate_ai_feature rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.transient_retry import retry_transient
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
        """
        Undo grant rows touched during a failed sync.

        Retries each restore/delete on transient failures. Raises if any
        grant still cannot be rolled back after retries.
        """
        logger.warning(
            "Rolling back AI grant sync operation=%s estate_id=%s "
            "subscription_id=%s created_grant_ids=%s updated_grant_ids=%s",
            self.operation,
            self.estate_id,
            self.subscription_id,
            self.created_grant_ids,
            list(self.updated_grants.keys()),
        )
        failed: list[str] = []

        for grant_id, snapshot in self.updated_grants.items():
            try:
                await retry_transient(
                    lambda gid=grant_id, snap=snapshot: (
                        repo.update_estate_ai_feature(gid, snap)
                    ),
                    attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
                    base_delay_seconds=(
                        settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
                    ),
                    operation_name=(
                        f"rollback_grant_update:{grant_id}:{self.operation}"
                    ),
                )
                logger.info(
                    "Rolled back estate_ai_feature update grant_id=%s "
                    "estate_id=%s subscription_id=%s operation=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                )
            except Exception:
                failed.append(grant_id)
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
                await retry_transient(
                    lambda gid=grant_id: repo.delete_estate_ai_feature(gid),
                    attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
                    base_delay_seconds=(
                        settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
                    ),
                    operation_name=(
                        f"rollback_grant_create:{grant_id}:{self.operation}"
                    ),
                )
                logger.info(
                    "Rolled back estate_ai_feature create grant_id=%s "
                    "estate_id=%s subscription_id=%s operation=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                )
            except Exception:
                failed.append(grant_id)
                logger.exception(
                    "Failed to rollback estate_ai_feature create "
                    "grant_id=%s estate_id=%s subscription_id=%s "
                    "operation=%s",
                    grant_id,
                    self.estate_id,
                    self.subscription_id,
                    self.operation,
                )

        if failed:
            raise RuntimeError(
                "AI grant rollback incomplete after retries "
                f"operation={self.operation} estate_id={self.estate_id} "
                f"subscription_id={self.subscription_id} "
                f"failed_grant_ids={failed}"
            )


async def setup_standalone_ai_subscription(
    repo: DbRevenueRepository,
    paystack: PaystackClient,
    *,
    grant: dict[str, Any],
    ai_feature: dict[str, Any],
    customer_email: str,
    authorization_code: str,
    amount_kobo: int,
    billing_interval: str,
    currency: str = "NGN",
) -> None:
    """
    Wire a Paystack Plan + Subscription for a standalone AI grant.

    Creates a new plan if one doesn't already exist for the feature, then
    creates a subscription so future charges are handled automatically.
    Failures are logged but do not propagate — the grant is already active.

    Args:
        repo: db-service HTTP repository.
        paystack: Paystack API client.
        grant: The newly provisioned estate_ai_feature row.
        ai_feature: The ai_feature catalog row for this grant.
        customer_email: Paystack customer email (from the charge event).
        authorization_code: Reusable card authorization code.
        amount_kobo: Charge amount in the smallest currency unit.
        billing_interval: Paystack interval string (e.g. "monthly").
        currency: ISO currency code (default "NGN").
    """
    feature_id = str(ai_feature["id"])
    feature_name = ai_feature.get("name") or ai_feature.get("feature_key", "")
    plan_code: str = ai_feature.get("paystack_plan_code") or ""
    try:
        if not plan_code:
            plan_data = await paystack.create_plan(
                name=f"GatePass AI - {feature_name} - {billing_interval}",
                amount_kobo=amount_kobo,
                interval=billing_interval,
                currency=currency,
            )
            plan_code = plan_data["plan_code"]
            await repo.update_ai_feature(
                feature_id, {"paystack_plan_code": plan_code}
            )
            logger.info(
                "Created Paystack plan for AI feature feature_id=%s "
                "plan_code=%s",
                feature_id,
                plan_code,
            )

        sub_data = await paystack.create_subscription(
            customer_email=customer_email,
            plan_code=plan_code,
            authorization_code=authorization_code,
        )
        subscription_code: str = sub_data["subscription_code"]
        await repo.update_estate_ai_feature(
            str(grant["id"]), {"paystack_subscription_code": subscription_code}
        )
        logger.info(
            "Standalone AI subscription set up grant_id=%s "
            "feature_id=%s subscription_code=%s plan_code=%s",
            grant["id"],
            feature_id,
            subscription_code,
            plan_code,
        )
    except Exception:
        logger.exception(
            "Failed to set up standalone AI subscription grant_id=%s "
            "feature_id=%s — grant is active but auto-renew will not work",
            grant["id"],
            feature_id,
        )


async def sync_tier_ai_grants(
    repo: DbRevenueRepository,
    *,
    estate_id: str,
    subscription_id: str,
    tier: dict[str, Any],
    period_end: datetime,
    extra_feature_keys: list[str] | None = None,
    paystack: PaystackClient | None = None,
) -> None:
    """
    Upsert estate_ai_feature rows for tier.included_ai_features (+ extras).

    Existing grants keep ``is_installed``. New grants are installed.
    Paid grants get ``expires_at=period_end``.

    When a tier grant supersedes an active standalone_purchase grant for the
    same feature, the standalone Paystack subscription is disabled (best-
    effort) and the standalone grant is marked cancelled. The tier grant takes
    over access going forward.

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
                # If the existing grant is an active standalone_purchase,
                # supersede it: disable the Paystack subscription (best-effort)
                # and mark it cancelled. The tier grant takes over.
                if (
                    str(grant.get("source") or "") == "standalone_purchase"
                    and str(grant.get("status") or "") == "active"
                ):
                    standalone_sub_code = grant.get(
                        "paystack_subscription_code"
                    )
                    if standalone_sub_code and paystack:
                        try:
                            await paystack.disable_subscription(
                                standalone_sub_code
                            )
                        except Exception:
                            logger.exception(
                                "Failed to disable standalone Paystack "
                                "subscription on tier upgrade "
                                "grant_id=%s subscription_code=%s — "
                                "proceeding with tier grant activation",
                                grant["id"],
                                standalone_sub_code,
                            )
                    await repo.update_estate_ai_feature(
                        str(grant["id"]),
                        {"auto_renew": False, "status": "cancelled"},
                    )
                    # Create a fresh tier grant below rather than updating
                    # the cancelled standalone row.
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
                    continue

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
        try:
            await rollback.apply(repo)
        except Exception:
            logger.exception(
                "AI grant sync rollback failed after retries "
                "estate_id=%s subscription_id=%s tier_id=%s touched=%s",
                estate_id,
                subscription_id,
                tier_id,
                rollback.touched_ids(),
            )
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
        try:
            await rollback.apply(repo)
        except Exception:
            logger.exception(
                "AI grant extend rollback failed after retries "
                "estate_id=%s subscription_id=%s touched=%s",
                estate_id,
                subscription_id,
                rollback.touched_ids(),
            )
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
