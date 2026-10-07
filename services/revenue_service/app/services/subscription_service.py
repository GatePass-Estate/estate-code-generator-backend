"""Estate subscription lookups and lifecycle mutations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
from app.services.pricing_service import (
    VAT_KEY,
    apply_vat,
    compute_ai_monthly,
    compute_price_per_seat,
    extract_included_keys,
    omit_vat,
    round_charge,
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
    "pending_tier_slug",
    "pending_covered_users",
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
        """Return subscription, tier, and entitlements (vat omitted)."""
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
        if subscription and isinstance(subscription.get("entitlements"), dict):
            subscription = {
                **subscription,
                "entitlements": omit_vat(subscription["entitlements"]),
            }
        if tier and isinstance(tier.get("entitlements"), dict):
            tier = {**tier, "entitlements": omit_vat(tier["entitlements"])}
        covered_users = (
            int((subscription or {}).get("covered_users") or 0) or None
        )
        pending_covered_users = (subscription or {}).get(
            "pending_covered_users"
        )
        effective_covered_users = (
            pending_covered_users
            if pending_covered_users is not None
            else covered_users
        )
        return {
            "estate_id": estate_id,
            "subscription": subscription,
            "tier": tier,
            "effective_entitlements": omit_vat(entitlements),
            "covered_users": covered_users,
            "pending_covered_users": pending_covered_users,
            "effective_covered_users": effective_covered_users,
        }

    async def get_billing_cycle(self, estate_id: str) -> dict:
        """Return next billing cycle projection for an estate.

        Complements GET /estate/{estate_id} (which returns the full
        subscription + entitlements) by adding what the next auto-
        renewal will charge and under which tier.

        Returns a minimal dict keyed only on ``estate_id`` when no
        active subscription exists.
        """
        subscription = await self.repo.get_active_subscription(estate_id)
        if not subscription:
            return {"estate_id": estate_id}

        auto_renew = bool(subscription.get("auto_renew"))
        period_end_raw = subscription.get("period_end")

        tier_id = str(subscription.get("tier_id") or "")
        current_tier = (
            await self.repo.get_tier_by_id(tier_id) if tier_id else None
        )

        # Resolve the tier that will apply at next renewal.
        pending_slug = subscription.get("pending_tier_slug") or ""
        tier_change_scheduled = bool(pending_slug)
        if tier_change_scheduled:
            next_tier = await self.repo.get_tier_by_slug(pending_slug)
            if not next_tier:
                logger.warning(
                    "get_billing_cycle: pending_tier_slug=%r not "
                    "found for estate_id=%s — treating as no change",
                    pending_slug,
                    estate_id,
                )
                tier_change_scheduled = False
                next_tier = current_tier
        else:
            next_tier = current_tier

        # Compute next billing amount only when auto-renew is on
        # and we have a resolvable next tier.
        next_billing_amount: float | None = None
        next_billing_currency: str | None = None

        if auto_renew and next_tier and not next_tier.get("is_custom"):
            try:
                # Late import to avoid circular dependency;
                # CheckoutService does not import SubscriptionService.
                from app.services.checkout_service import (
                    CheckoutService,
                )

                checkout_svc = CheckoutService(self.repo)
                (
                    _country,
                    service_prices,
                    _ai_prices,
                    currency,
                    vat_rate,
                ) = await checkout_svc._pricing_context(estate_id)

                entitlements = dict(next_tier.get("entitlements") or {})
                included_keys = [
                    k
                    for k, v in entitlements.items()
                    if k != VAT_KEY
                    and (
                        (isinstance(v, bool) and v)
                        or (isinstance(v, int) and v > 0)
                    )
                ]
                seat_result = compute_price_per_seat(
                    service_prices, included_keys
                )
                price_per_seat = seat_result["price_per_seat"]
                # Use pending_covered_users if a seat reduction is scheduled,
                # since that is the seat count that will be charged at renewal.
                pending_seats_next = subscription.get("pending_covered_users")
                covered_users = int(
                    pending_seats_next
                    if pending_seats_next is not None
                    else (subscription.get("covered_users") or 1)
                )

                period_start_raw = subscription.get("period_start")
                if period_end_raw and period_start_raw:
                    period_end_dt = datetime.fromisoformat(
                        str(period_end_raw).replace("Z", "+00:00")
                    )
                    period_start_dt = datetime.fromisoformat(
                        str(period_start_raw).replace("Z", "+00:00")
                    )
                    period_days = (
                        period_end_dt.date() - period_start_dt.date()
                    ).days + 1
                    period_months = max(1, round(period_days / 30))
                else:
                    period_months = 1

                subtotal = round_charge(
                    price_per_seat * covered_users * period_months
                )
                vat_result = apply_vat(subtotal, vat_rate or 0)
                next_billing_amount = float(vat_result["client_total"])
                next_billing_currency = currency
            except Exception:
                logger.exception(
                    "get_billing_cycle: failed to compute "
                    "next_billing_amount estate_id=%s",
                    estate_id,
                )

        def _to_str(v: Any) -> str | None:
            if v is None:
                return None
            return v.isoformat() if hasattr(v, "isoformat") else str(v)

        pending_covered_users_next = subscription.get("pending_covered_users")
        seat_reduction_scheduled = pending_covered_users_next is not None
        next_covered_users = (
            int(pending_covered_users_next)
            if seat_reduction_scheduled
            else int(subscription.get("covered_users") or 1)
        )
        return {
            "estate_id": estate_id,
            "period_end": _to_str(period_end_raw),
            "covered_users": subscription.get("covered_users"),
            "auto_renew": auto_renew,
            "current_tier_slug": (
                current_tier.get("slug") if current_tier else None
            ),
            "next_renewal_date": _to_str(period_end_raw),
            "tier_change_scheduled": tier_change_scheduled,
            "next_tier_slug": (next_tier.get("slug") if next_tier else None),
            "next_tier": (
                {
                    **next_tier,
                    "entitlements": omit_vat(next_tier.get("entitlements")),
                }
                if next_tier
                else None
            ),
            "seat_reduction_scheduled": seat_reduction_scheduled,
            "next_covered_users": next_covered_users,
            "next_billing_amount": next_billing_amount,
            "next_billing_currency": next_billing_currency,
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
            "pending_tier_slug": None,  # Clear any stale scheduled tier change
            "pending_covered_users": None,  # Clear any stale scheduled seat reduction
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

        # Apply a pending tier change if one was scheduled.
        pending_slug = subscription.get("pending_tier_slug")
        pending_tier: dict | None = None
        update_payload: dict[str, Any] = {
            "status": "active",
            "period_end": new_end.isoformat(),
            "auto_renew": True,
            "cancelled_at": None,
            "pre_expiry_notified": False,
        }
        if pending_slug:
            pending_tier = await self.repo.get_tier_by_slug(pending_slug)
            if pending_tier:
                update_payload["tier_id"] = pending_tier["id"]
                update_payload["pending_tier_slug"] = None
                logger.info(
                    "Applying pending tier change estate_id=%s "
                    "pending_slug=%s new_tier_id=%s",
                    estate_id,
                    pending_slug,
                    pending_tier["id"],
                )
            else:
                logger.warning(
                    "Pending tier slug %r not found for estate_id=%s "
                    "— clearing stale pending_tier_slug",
                    pending_slug,
                    estate_id,
                )
                update_payload["pending_tier_slug"] = None

        # Apply a pending seat reduction if one was scheduled.
        pending_seats = subscription.get("pending_covered_users")
        if pending_seats is not None:
            update_payload["covered_users"] = pending_seats
            update_payload["pending_covered_users"] = None
            logger.info(
                "Applying pending seat reduction estate_id=%s new_seats=%s",
                estate_id,
                pending_seats,
            )

        updated = await self.repo.update_estate_subscription(
            subscription_id, update_payload
        )
        try:
            if pending_tier:
                await retry_transient(
                    lambda: sync_tier_ai_grants(
                        self.repo,
                        estate_id=estate_id,
                        subscription_id=subscription_id,
                        tier=pending_tier,
                        period_end=new_end,
                    ),
                    attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
                    base_delay_seconds=(
                        settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
                    ),
                    operation_name="renew_sync_tier_ai_grants",
                )
            else:
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

        if call_paystack:
            sub_code = subscription.get("paystack_subscription_code")
            if sub_code and self._paystack:
                # Disable Paystack first — if this fails we have not touched
                # our DB yet, so the caller can safely retry.
                await self._paystack.disable_subscription(sub_code)
                logger.info(
                    "Paystack subscription disabled estate_id=%s "
                    "subscription_code=%s",
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

        now = datetime.now(tz=timezone.utc)
        updated = await self.repo.update_estate_subscription(
            str(subscription["id"]),
            {
                "auto_renew": False,
                "status": "cancelled",
                "cancelled_at": now.isoformat(),
            },
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
        update_payload: dict[str, Any] = {
            "covered_users": current + seats_added,
        }
        if subscription.get("pending_covered_users") is not None:
            update_payload["pending_covered_users"] = None
        updated = await self.repo.update_estate_subscription(
            str(subscription["id"]),
            update_payload,
        )
        return {
            "estate_id": estate_id,
            "covered_users": current + seats_added,
            "subscription": updated,
        }

    async def change_tier_immediate(
        self,
        estate_id: str,
        new_tier_slug: str,
        paid_at: datetime,
    ) -> dict:
        """Upgrade to a new tier immediately after a prorated payment.

        Updates subscription tier_id, syncs AI grants for the new tier,
        and resets pre_expiry_notified. The Paystack plan amount update
        is handled by the webhook caller (best-effort, with the session
        amount already available there).
        """
        active_sub = await self.repo.get_active_subscription(estate_id)
        if not active_sub:
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )

        new_tier = await self.repo.get_tier_by_slug(new_tier_slug)
        if not new_tier:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown tier '{new_tier_slug}'",
            )

        subscription_id = str(active_sub["id"])
        period_end_raw = active_sub.get("period_end")
        period_end = datetime.fromisoformat(
            str(period_end_raw).replace("Z", "+00:00")
        )
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)

        updated = await self.repo.update_estate_subscription(
            subscription_id,
            {
                "tier_id": new_tier["id"],
                "pre_expiry_notified": False,
                "pending_tier_slug": None,  # Clear any stale scheduled change
            },
        )

        try:
            await retry_transient(
                lambda: sync_tier_ai_grants(
                    self.repo,
                    estate_id=estate_id,
                    subscription_id=subscription_id,
                    tier=new_tier,
                    period_end=period_end,
                ),
                attempts=settings.REVENUE_TRANSIENT_RETRY_ATTEMPTS,
                base_delay_seconds=(
                    settings.REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS
                ),
                operation_name="tier_change_immediate_sync_ai_grants",
            )
        except Exception as exc:
            logger.exception(
                "AI grant sync failed after immediate tier change; "
                "reverting tier_id estate_id=%s subscription_id=%s "
                "new_tier_slug=%s",
                estate_id,
                subscription_id,
                new_tier_slug,
            )
            prior_tier_id = active_sub.get("tier_id")
            try:
                await self.repo.update_estate_subscription(
                    subscription_id,
                    {
                        "tier_id": prior_tier_id,
                        "pre_expiry_notified": active_sub.get(
                            "pre_expiry_notified", False
                        ),
                        # Restore any scheduled tier change that was cleared
                        # so the user's expected downgrade/upgrade is not
                        # silently dropped on a failed immediate upgrade.
                        "pending_tier_slug": active_sub.get(
                            "pending_tier_slug"
                        ),
                    },
                )
            except Exception:
                logger.exception(
                    "Revert of tier change also failed estate_id=%s "
                    "subscription_id=%s",
                    estate_id,
                    subscription_id,
                )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Tier upgrade reverted because AI grant sync failed; "
                    "retry once db-service is healthy."
                ),
            ) from exc

        logger.info(
            "Immediate tier upgrade applied estate_id=%s "
            "subscription_id=%s new_tier_slug=%s paid_at=%s",
            estate_id,
            subscription_id,
            new_tier_slug,
            paid_at.isoformat(),
        )
        return {
            "estate_id": estate_id,
            "subscription_id": subscription_id,
            "subscription": updated,
            "tier_slug": new_tier_slug,
        }

    async def _update_paystack_plan_for_tier(
        self,
        *,
        estate_id: str,
        tier: dict,
        active_sub: dict,
        sub_code: str,
    ) -> None:
        """Best-effort Paystack plan amount update for a tier change.

        Computes the full-period price for ``tier`` (seat price ×
        covered_users × period_months) and updates the Paystack plan so
        the next auto-renewal charges the correct amount. Logs and returns
        silently on any failure — the DB change is already committed.
        """
        # Late import avoids a circular dependency; CheckoutService does
        # not import SubscriptionService.
        from app.services.checkout_service import CheckoutService

        try:
            checkout_svc = CheckoutService(self.repo)
            # Paystack plan amount is pre-VAT; VAT is applied at checkout only.
            (
                _country,
                service_prices,
                _ai_prices,
                _currency,
                _vat,
            ) = await checkout_svc._pricing_context(estate_id)
            entitlements = dict(tier.get("entitlements") or {})
            included_keys = [
                k
                for k, v in entitlements.items()
                if k != VAT_KEY
                and (
                    (isinstance(v, bool) and v)
                    or (isinstance(v, int) and v > 0)
                )
            ]
            seat_result = compute_price_per_seat(service_prices, included_keys)
            price_per_seat = Decimal(str(seat_result["price_per_seat"]))
            covered_users = int(active_sub.get("covered_users") or 1)
            period_end_raw = active_sub.get("period_end")
            period_start_raw = active_sub.get("period_start")
            if period_end_raw and period_start_raw:
                period_end_dt = datetime.fromisoformat(
                    str(period_end_raw).replace("Z", "+00:00")
                )
                period_start_dt = datetime.fromisoformat(
                    str(period_start_raw).replace("Z", "+00:00")
                )
                period_days = (
                    period_end_dt.date() - period_start_dt.date()
                ).days + 1
                period_months = max(1, round(period_days / 30))
            else:
                period_months = 1

            new_amount_kobo = int(
                price_per_seat * covered_users * period_months * 100
            )

            if not self._paystack:
                return
            sub_data = await self._paystack.get_subscription(sub_code)
            plan_code = (sub_data.get("plan") or {}).get("plan_code", "")
            if not plan_code:
                return
            interval = (sub_data.get("plan") or {}).get("interval", "monthly")
            tier_slug = tier.get("slug", "")
            await self._paystack.update_plan(
                plan_code,
                amount_kobo=new_amount_kobo,
                name=(
                    f"GatePass - {tier_slug} - "
                    f"{covered_users} seats - {interval}"
                ),
            )
            logger.info(
                "Updated Paystack plan for tier change estate_id=%s "
                "plan_code=%s tier=%s new_amount_kobo=%s",
                estate_id,
                plan_code,
                tier_slug,
                new_amount_kobo,
            )
        except Exception:
            logger.exception(
                "Failed to update Paystack plan for tier change "
                "estate_id=%s tier=%s — DB updated but "
                "auto-renewal amount may be stale",
                estate_id,
                tier.get("slug"),
            )

    async def schedule_tier_change(
        self,
        estate_id: str,
        tier_slug: str,
    ) -> dict:
        """Schedule a tier change to take effect on the next renewal.

        Stores ``pending_tier_slug`` on the active subscription. Returns
        the active subscription, current tier, and new tier so the caller
        can do a best-effort Paystack plan amount update.
        """
        active_sub = await self.repo.get_active_subscription(estate_id)
        if not active_sub or active_sub.get("status") not in (
            "active",
            "trialing",
        ):
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        if not active_sub.get("auto_renew"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Auto-renewal is off — purchase the new tier directly "
                    "when you are ready to renew."
                ),
            )

        current_tier = await self.repo.get_tier_by_id(
            str(active_sub["tier_id"])
        )
        new_tier = await self.repo.get_tier_by_slug(tier_slug)
        if not new_tier:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown tier '{tier_slug}'",
            )
        if new_tier.get("is_custom"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Custom tier changes require negotiated entitlements. "
                    "Use the custom checkout flow instead."
                ),
            )
        if str(new_tier["id"]) == str(active_sub["tier_id"]):
            raise HTTPException(
                status_code=400,
                detail="Target tier is the same as the current tier",
            )

        await self.repo.update_estate_subscription(
            str(active_sub["id"]),
            {"pending_tier_slug": tier_slug},
        )
        logger.info(
            "Scheduled tier change estate_id=%s "
            "current_tier=%s pending_tier=%s effective_from=%s",
            estate_id,
            current_tier.get("slug") if current_tier else None,
            tier_slug,
            active_sub.get("period_end"),
        )

        sub_code = active_sub.get("paystack_subscription_code")
        if sub_code:
            await self._update_paystack_plan_for_tier(
                estate_id=estate_id,
                tier=new_tier,
                active_sub=active_sub,
                sub_code=sub_code,
            )

        return {
            "estate_id": estate_id,
            "pending_tier_slug": tier_slug,
            "effective_from": active_sub.get("period_end"),
        }

    async def cancel_tier_change(self, estate_id: str) -> dict:
        """Cancel a scheduled tier change (clears pending_tier_slug).

        Returns the subscription and current tier so the caller can
        revert the Paystack plan amount.
        """
        active_sub = await self.repo.get_active_subscription(estate_id)
        if not active_sub:
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        if not active_sub.get("pending_tier_slug"):
            raise HTTPException(
                status_code=400,
                detail="No pending tier change to cancel",
            )

        current_tier = await self.repo.get_tier_by_id(
            str(active_sub["tier_id"])
        )
        await self.repo.update_estate_subscription(
            str(active_sub["id"]),
            {"pending_tier_slug": None},
        )
        logger.info(
            "Cancelled tier change estate_id=%s "
            "current_tier=%s cancelled_pending=%s",
            estate_id,
            current_tier.get("slug") if current_tier else None,
            active_sub.get("pending_tier_slug"),
        )

        sub_code = active_sub.get("paystack_subscription_code")
        if sub_code and current_tier:
            await self._update_paystack_plan_for_tier(
                estate_id=estate_id,
                tier=current_tier,
                active_sub=active_sub,
                sub_code=sub_code,
            )

        return {
            "estate_id": estate_id,
            "pending_tier_slug": None,
        }

    # ── Seat reduction ────────────────────────────────────────────────────

    async def get_seat_reduction_eligibility(self, estate_id: str) -> dict:
        """Return whether a seat reduction is possible and the minimum seat count."""
        sub = await self.repo.get_active_subscription(estate_id)
        if not sub or (sub.get("status") or "").lower() not in (
            "active",
            "trialing",
        ):
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        current_seats = int(sub.get("covered_users") or 1)
        active_users = await self.repo.get_estate_active_user_count(estate_id)
        can_reduce = (
            bool(sub.get("auto_renew")) and current_seats > active_users
        )
        return {
            "estate_id": estate_id,
            "can_reduce": can_reduce,
            "current_seats": current_seats,
            "active_users": active_users,
            "min_allowed_seats": active_users,
        }

    async def schedule_seat_reduction(
        self, estate_id: str, new_seats: int
    ) -> dict:
        """Schedule a seat reduction to take effect on the next renewal.

        Guards (in order):
        1. Active subscription must exist and be ``active`` or ``trialing``.
        2. ``new_seats >= 1``
        3. ``new_seats < current covered_users`` (must be an actual reduction).
        4. ``new_seats >= active_user_count`` (cannot evict existing members).

        Stores ``pending_covered_users`` on the subscription and updates the
        Paystack plan amount best-effort so the next auto-charge reflects the
        lower seat count.
        """
        sub = await self.repo.get_active_subscription(estate_id)
        if not sub or (sub.get("status") or "").lower() not in (
            "active",
            "trialing",
        ):
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        if not sub.get("auto_renew"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Auto-renewal is off — reduce seats when you are "
                    "ready to purchase a new subscription."
                ),
            )
        current_seats = int(sub.get("covered_users") or 1)
        if new_seats < 1:
            raise HTTPException(
                status_code=400, detail="new seats must be >= 1"
            )
        if new_seats >= current_seats:
            raise HTTPException(
                status_code=400,
                detail=(
                    "new seats must be less than the current seat count "
                    f"({current_seats})"
                ),
            )
        active_users = await self.repo.get_estate_active_user_count(estate_id)
        if new_seats < active_users:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot reduce below active user count ({active_users}). "
                    "Remove users first or choose a higher seat count."
                ),
            )

        await self.repo.update_estate_subscription(
            str(sub["id"]), {"pending_covered_users": new_seats}
        )
        logger.info(
            "Scheduled seat reduction estate_id=%s new_seats=%s "
            "current_seats=%s active_users=%s",
            estate_id,
            new_seats,
            current_seats,
            active_users,
        )

        sub_code = sub.get("paystack_subscription_code")
        if sub_code:
            await self._update_paystack_plan_for_seat_reduction(
                estate_id=estate_id,
                active_sub=sub,
                new_seats=new_seats,
                sub_code=sub_code,
            )

        period_end_raw = sub.get("period_end")
        effective_from = (
            period_end_raw.isoformat()
            if hasattr(period_end_raw, "isoformat")
            else str(period_end_raw)
            if period_end_raw
            else None
        )
        return {
            "estate_id": estate_id,
            "pending_covered_users": new_seats,
            "effective_from": effective_from,
        }

    async def cancel_seat_reduction(self, estate_id: str) -> dict:
        """Cancel a scheduled seat reduction (clears pending_covered_users)."""
        sub = await self.repo.get_active_subscription(estate_id)
        if not sub:
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )
        if sub.get("pending_covered_users") is None:
            raise HTTPException(
                status_code=400,
                detail="No seat reduction is scheduled",
            )

        current_seats = int(sub.get("covered_users") or 1)
        await self.repo.update_estate_subscription(
            str(sub["id"]), {"pending_covered_users": None}
        )
        logger.info(
            "Cancelled seat reduction estate_id=%s "
            "cancelled_pending_seats=%s current_seats=%s",
            estate_id,
            sub.get("pending_covered_users"),
            current_seats,
        )

        # Best-effort revert Paystack plan to current covered_users
        sub_code = sub.get("paystack_subscription_code")
        if sub_code:
            await self._update_paystack_plan_for_seat_reduction(
                estate_id=estate_id,
                active_sub=sub,
                new_seats=current_seats,
                sub_code=sub_code,
            )

        return {
            "estate_id": estate_id,
            "pending_covered_users": None,
            "effective_from": None,
        }

    async def _update_paystack_plan_for_seat_reduction(
        self,
        *,
        estate_id: str,
        active_sub: dict,
        new_seats: int,
        sub_code: str,
    ) -> None:
        """Best-effort Paystack plan amount update for a seat count change.

        Computes the full-period price for ``new_seats`` seats at the current
        tier's rate and updates the Paystack plan so the next auto-renewal
        charges the correct amount. Logs and returns silently on any failure.
        """
        from app.services.checkout_service import CheckoutService

        try:
            checkout_svc = CheckoutService(self.repo)
            (
                _country,
                service_prices,
                ai_prices,
                _currency,
                vat_rate,
            ) = await checkout_svc._pricing_context(estate_id)

            tier_id = str(active_sub.get("tier_id") or "")
            tier = await self.repo.get_tier_by_id(tier_id) if tier_id else None
            if not tier:
                return
            if tier.get("is_custom"):
                return  # Custom tier has negotiated pricing; do not overwrite plan amount

            entitlements = dict(tier.get("entitlements") or {})
            included_keys = extract_included_keys(entitlements)
            seat_result = compute_price_per_seat(service_prices, included_keys)
            price_per_seat = Decimal(str(seat_result["price_per_seat"]))

            ai_keys = list(tier.get("included_ai_features") or [])
            ai_monthly = Decimal(0)
            if ai_keys:
                ai_result = compute_ai_monthly(ai_prices, ai_keys)
                ai_monthly = Decimal(str(ai_result["ai_price_per_month"]))

            period_end_raw = active_sub.get("period_end")
            period_start_raw = active_sub.get("period_start")
            if period_end_raw and period_start_raw:
                period_end_dt = datetime.fromisoformat(
                    str(period_end_raw).replace("Z", "+00:00")
                )
                period_start_dt = datetime.fromisoformat(
                    str(period_start_raw).replace("Z", "+00:00")
                )
                period_days = (
                    period_end_dt.date() - period_start_dt.date()
                ).days + 1
                period_months = max(1, round(period_days / 30))
            else:
                period_months = 1

            subtotal = round_charge(
                (price_per_seat * new_seats + ai_monthly)
                * Decimal(period_months)
            )
            vat = apply_vat(subtotal, vat_rate)
            new_amount_kobo = int(Decimal(str(vat["client_total"])) * 100)

            if not self._paystack:
                return
            sub_data = await self._paystack.get_subscription(sub_code)
            plan_code = (sub_data.get("plan") or {}).get("plan_code", "")
            if not plan_code:
                return
            interval = (sub_data.get("plan") or {}).get("interval", "monthly")
            tier_slug = tier.get("slug", "")
            await self._paystack.update_plan(
                plan_code,
                amount_kobo=new_amount_kobo,
                name=(
                    f"GatePass - {tier_slug} - "
                    f"{new_seats} seats - {interval}"
                ),
            )
            logger.info(
                "Updated Paystack plan for seat change estate_id=%s "
                "plan_code=%s tier=%s new_seats=%s new_amount_kobo=%s",
                estate_id,
                plan_code,
                tier_slug,
                new_seats,
                new_amount_kobo,
            )
        except Exception:
            logger.exception(
                "Failed to update Paystack plan for seat change "
                "estate_id=%s new_seats=%s — DB updated but "
                "auto-renewal amount may be stale",
                estate_id,
                new_seats,
            )
