"""Estate subscription lookups and lifecycle mutations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.entitlement_validation import ensure_admin_fee_entitlement
from app.libs.period_dating import compute_period_end
from app.libs.transient_retry import retry_transient
from app.repositories.db_revenue import DbRevenueRepository
from app.services.ai_grant_sync import (
    extend_subscription_ai_grants,
    sync_tier_ai_grants,
)
from app.services.entitlement_resolver import (
    PAID_ACCESS_STATUSES,
    resolve_entitlements,
)

logger = logging.getLogger(__name__)

# Subscription writes and AI grant sync are separate HTTP calls to db-service
# (no distributed transaction). activate/renew retry grant sync on transient
# failures, then compensate on persistent failure. Compensation is also
# retried; grant sync itself is idempotent for safe retry.
_SUBSCRIPTION_ROLLBACK_FIELDS = (
    "tier_id",
    "status",
    "period_start",
    "period_end",
    "auto_renew",
    "covered_users",
    "entitlements",
    "cancelled_at",
)


def _subscription_rollback_payload(subscription: dict) -> dict[str, Any]:
    return {
        field: subscription.get(field)
        for field in _SUBSCRIPTION_ROLLBACK_FIELDS
    }


async def _compensate_subscription_write(
    repo: DbRevenueRepository,
    *,
    estate_id: str,
    subscription_id: str,
    created_new: bool,
    prior_state: dict[str, Any] | None,
    operation: str,
) -> None:
    """Undo a subscription row written before grant sync failed (with retries)."""
    prior_tier_id = (prior_state or {}).get("tier_id")
    logger.warning(
        "Compensating subscription write operation=%s estate_id=%s "
        "subscription_id=%s created_new=%s prior_tier_id=%s "
        "prior_status=%s prior_period_end=%s",
        operation,
        estate_id,
        subscription_id,
        created_new,
        prior_tier_id,
        (prior_state or {}).get("status"),
        (prior_state or {}).get("period_end"),
    )

    async def _do_compensate() -> None:
        if created_new:
            await repo.delete_estate_subscription(subscription_id)
            return
        if prior_state:
            await repo.update_estate_subscription(
                subscription_id,
                _subscription_rollback_payload(prior_state),
            )

    try:
        await retry_transient(
            _do_compensate,
            attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
            base_delay_seconds=(
                settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
            ),
            operation_name=f"compensate_subscription:{operation}",
        )
        if created_new:
            logger.info(
                "Rolled back created estate_subscription id=%s "
                "estate_id=%s operation=%s",
                subscription_id,
                estate_id,
                operation,
            )
        elif prior_state:
            logger.info(
                "Restored estate_subscription id=%s estate_id=%s "
                "operation=%s prior_tier_id=%s",
                subscription_id,
                estate_id,
                operation,
                prior_tier_id,
            )
    except Exception:
        logger.exception(
            "Subscription compensation failed operation=%s estate_id=%s "
            "subscription_id=%s created_new=%s prior_tier_id=%s "
            "prior_state=%s",
            operation,
            estate_id,
            subscription_id,
            created_new,
            prior_tier_id,
            {
                field: (prior_state or {}).get(field)
                for field in _SUBSCRIPTION_ROLLBACK_FIELDS
            },
        )
        raise


class SubscriptionService:
    """Reads and mutates estate subscriptions and linked AI grants."""

    def __init__(
        self,
        repo: DbRevenueRepository,
        paystack_client: PaystackClient | None = None,
    ):
        self.repo = repo
        self._paystack = paystack_client

    async def get_estate_subscription(self, estate_id: str) -> dict:
        """Return subscription, tier, and effective entitlements for an estate."""
        subscription = await self.repo.get_active_subscription(estate_id)
        tier = None
        if subscription:
            tier = await self.repo.get_tier_by_id(str(subscription["tier_id"]))

        status = ((subscription or {}).get("status") or "").lower()
        needs_access_fallback = (
            not subscription or status not in PAID_ACCESS_STATUSES or not tier
        )

        access_tier = None
        if needs_access_fallback:
            access_tier = await self.repo.get_tier_by_slug("access")
            if not access_tier:
                raise HTTPException(
                    status_code=500, detail="Access tier not seeded"
                )

        entitlements = resolve_entitlements(
            subscription=subscription,
            tier=tier,
            access_tier=access_tier,
        )
        return {
            "estate_id": estate_id,
            "subscription": subscription,
            "tier": tier,
            "effective_entitlements": entitlements,
        }

    async def _latest_subscription(self, estate_id: str) -> dict | None:
        items = await self.repo.list_estate_subscriptions(estate_id)
        if not items:
            return None
        # Prefer active/trialing/past_due, else most recently created
        for status in (
            "active",
            "trialing",
            "past_due",
            "cancelled",
            "expired",
        ):
            for item in items:
                if (item.get("status") or "").lower() == status:
                    return item
        return items[0]

    async def activate(self, request: dict[str, Any]) -> dict:
        """
        Activate (or replace) a paid subscription after charge success.

        Writes custom entitlements snapshot when the tier is custom.
        Syncs tier AI grants onto estate_ai_feature.

        Subscription and grant sync are separate db-service calls; grant sync
        is retried on transient failures, rolls back its own partial writes,
        and the subscription write is compensated (also with retries) if grant
        sync still fails. Both sync and compensate are safe to retry.
        """
        estate_id = request["estate_id"]
        tier_slug = request["tier_slug"]
        covered_users = int(request["covered_users"])
        period_months = int(request["period_months"])
        entitlements = request.get("entitlements")
        ai_feature_keys = list(request.get("ai_feature_keys") or [])

        tier = await self.repo.get_tier_by_slug(tier_slug)
        if not tier:
            raise HTTPException(
                status_code=404, detail=f"Unknown tier '{tier_slug}'"
            )

        if tier.get("is_custom"):
            if entitlements is None:
                raise HTTPException(
                    status_code=400,
                    detail="Custom tier requires entitlements snapshot",
                )
            snapshot = ensure_admin_fee_entitlement(dict(entitlements))
            # Seat purchase is source of truth for max_active_users.
            snapshot["max_active_users"] = covered_users
        else:
            snapshot = None
            entitlements = tier.get("entitlements") or {}

        paid_at_raw = request.get("paid_at")
        if paid_at_raw:
            paid_at = datetime.fromisoformat(
                str(paid_at_raw).replace("Z", "+00:00")
            )
        else:
            paid_at = datetime.now(tz=timezone.utc)
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=timezone.utc)

        duration = timedelta(days=30 * period_months)
        period_end = compute_period_end(
            paid_at=paid_at,
            duration=duration,
            old_period_end=None,
            grace_days=settings.RENEWAL_GRACE_PERIOD_DAYS,
        )

        existing = await self.repo.get_active_subscription(estate_id)
        prior_state = dict(existing) if existing else None
        created_new = False
        payload = {
            "estate_id": estate_id,
            "tier_id": tier["id"],
            "status": "active",
            "period_start": paid_at.isoformat(),
            "period_end": period_end.isoformat(),
            "auto_renew": True,
            "covered_users": covered_users,
            "entitlements": snapshot,
            "cancelled_at": None,
        }

        if existing:
            subscription = await self.repo.update_estate_subscription(
                str(existing["id"]), payload
            )
            subscription_id = str(existing["id"])
        else:
            created = await self.repo.create_estate_subscription(payload)
            subscription_id = str(created["id"])
            subscription = created
            created_new = True

        try:
            await retry_transient(
                lambda: sync_tier_ai_grants(
                    self.repo,
                    estate_id=estate_id,
                    subscription_id=subscription_id,
                    tier=tier,
                    period_end=period_end,
                    extra_feature_keys=ai_feature_keys,
                ),
                attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
                base_delay_seconds=(
                    settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
                ),
                operation_name="activate_sync_tier_ai_grants",
            )
        except Exception as exc:
            logger.exception(
                "Activate grant sync failed; compensating subscription "
                "estate_id=%s subscription_id=%s tier_id=%s tier_slug=%s "
                "created_new=%s",
                estate_id,
                subscription_id,
                tier.get("id"),
                tier_slug,
                created_new,
            )
            try:
                await _compensate_subscription_write(
                    self.repo,
                    estate_id=estate_id,
                    subscription_id=subscription_id,
                    created_new=created_new,
                    prior_state=prior_state,
                    operation="activate",
                )
            except Exception as compensation_exc:
                logger.exception(
                    "Activate compensation failed estate_id=%s "
                    "subscription_id=%s tier_id=%s created_new=%s",
                    estate_id,
                    subscription_id,
                    tier.get("id"),
                    created_new,
                )
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Subscription activation updated AI grants "
                        "incompletely and automatic rollback failed; "
                        "retry grant sync or repair manually before "
                        "billing goes live."
                    ),
                ) from compensation_exc
            raise HTTPException(
                status_code=502,
                detail=(
                    "Subscription activation rolled back because AI grant sync"
                    " failed; retry the activation once db-service is healthy."
                ),
            ) from exc
        return {
            "estate_id": estate_id,
            "subscription_id": subscription_id,
            "subscription": subscription,
            "tier_slug": tier_slug,
            "entitlements_snapshot": snapshot,
            "effective_entitlements": entitlements
            if snapshot is None
            else snapshot,
            "period_end": period_end.isoformat(),
        }

    async def renew(
        self,
        estate_id: str,
        *,
        period_months: int = 1,
        paid_at: datetime | None = None,
    ) -> dict:
        """Renew subscription using dating rules; extend linked paid AI grants.

        Rolls back the subscription period update if
        linked grant extension fails.
        Grant extension is idempotent and safe to retry.
        """
        subscription = await self._latest_subscription(estate_id)
        if not subscription:
            raise HTTPException(
                status_code=404, detail="No subscription found for estate"
            )

        paid = paid_at or datetime.now(tz=timezone.utc)
        if paid.tzinfo is None:
            paid = paid.replace(tzinfo=timezone.utc)

        old_end_raw = subscription.get("period_end")
        old_end = None
        if old_end_raw:
            old_end = datetime.fromisoformat(
                str(old_end_raw).replace("Z", "+00:00")
            )

        duration = timedelta(days=30 * period_months)
        new_end = compute_period_end(
            paid_at=paid,
            duration=duration,
            old_period_end=old_end,
            grace_days=settings.RENEWAL_GRACE_PERIOD_DAYS,
        )

        prior_state = dict(subscription)
        subscription_id = str(subscription["id"])
        updated = await self.repo.update_estate_subscription(
            subscription_id,
            {
                "status": "active",
                "period_end": new_end.isoformat(),
                "auto_renew": True,
                "cancelled_at": None,
            },
        )
        try:
            await retry_transient(
                lambda: extend_subscription_ai_grants(
                    self.repo,
                    estate_id=estate_id,
                    subscription_id=subscription_id,
                    new_period_end=new_end,
                ),
                attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
                base_delay_seconds=(
                    settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
                ),
                operation_name="renew_extend_subscription_ai_grants",
            )
        except Exception as exc:
            logger.exception(
                "Renew grant sync failed; compensating subscription "
                "estate_id=%s subscription_id=%s tier_id=%s "
                "prior_period_end=%s attempted_period_end=%s",
                estate_id,
                subscription_id,
                subscription.get("tier_id"),
                prior_state.get("period_end"),
                new_end.isoformat(),
            )
            try:
                await _compensate_subscription_write(
                    self.repo,
                    estate_id=estate_id,
                    subscription_id=subscription_id,
                    created_new=False,
                    prior_state=prior_state,
                    operation="renew",
                )
            except Exception as compensation_exc:
                logger.exception(
                    "Renew compensation failed estate_id=%s "
                    "subscription_id=%s tier_id=%s prior_period_end=%s",
                    estate_id,
                    subscription_id,
                    subscription.get("tier_id"),
                    prior_state.get("period_end"),
                )
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Subscription renewal updated AI grants incompletely "
                        "and automatic rollback failed; retry grant extension "
                        "or repair manually before billing goes live."
                    ),
                ) from compensation_exc
            raise HTTPException(
                status_code=502,
                detail=(
                    "Subscription renewal rolled back because AI grant sync "
                    "failed; retry the renewal once db-service is healthy."
                ),
            ) from exc
        return {
            "estate_id": estate_id,
            "subscription": updated,
            "period_end": new_end.isoformat(),
        }

    async def cancel(
        self, estate_id: str, *, call_paystack: bool = True
    ) -> dict:
        """Cancel auto-renew; keep period_end / AI expires_at unchanged.

        Args:
            estate_id: Estate whose subscription to cancel.
            call_paystack: When True (default), also disables the Paystack
                recurring subscription so no further charges fire. Pass
                False when called from the ``subscription.disable`` webhook
                handler — Paystack already disabled it on their side.
        """
        subscription = await self.repo.get_active_subscription(estate_id)
        if not subscription:
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        now = datetime.now(tz=timezone.utc)
        updated = await self.repo.update_estate_subscription(
            str(subscription["id"]),
            {
                "auto_renew": False,
                "status": "cancelled",
                "cancelled_at": now.isoformat(),
            },
        )

        if call_paystack:
            sub_code = subscription.get("paystack_subscription_code")
            if sub_code and self._paystack:
                try:
                    await self._paystack.disable_subscription(sub_code)
                    logger.info(
                        "Paystack subscription disabled estate_id=%s "
                        "subscription_code=%s",
                        estate_id,
                        sub_code,
                    )
                except Exception:
                    # DB is already updated — log and continue. Ops must
                    # manually disable the Paystack subscription to stop
                    # further charges.
                    logger.exception(
                        "Failed to disable Paystack subscription "
                        "estate_id=%s subscription_code=%s — "
                        "cancelled in DB but Paystack may still charge",
                        estate_id,
                        sub_code,
                    )
            elif not sub_code:
                logger.warning(
                    "cancel estate_id=%s has no "
                    "paystack_subscription_code — cannot disable "
                    "Paystack subscription; it may continue charging",
                    estate_id,
                )

        return {"estate_id": estate_id, "subscription": updated}

    async def apply_seat_add(self, estate_id: str, seats_added: int) -> dict:
        """Bump covered_users after a successful mid-period seat purchase."""
        if seats_added < 1:
            raise HTTPException(
                status_code=400, detail="seats_added must be >= 1"
            )
        subscription = await self.repo.get_active_subscription(estate_id)
        if not subscription:
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        status = (subscription.get("status") or "").lower()
        if status not in ("active", "trialing"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot add seats to a subscription with "
                    f"status '{status}'. Only active or trialing "
                    "subscriptions allow mid-period seat additions."
                ),
            )
        current = int(subscription.get("covered_users") or 0)
        updated = await self.repo.update_estate_subscription(
            str(subscription["id"]),
            {"covered_users": current + seats_added},
        )
        return {
            "estate_id": estate_id,
            "covered_users": current + seats_added,
            "subscription": updated,
        }
