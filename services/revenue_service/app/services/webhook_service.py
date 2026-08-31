"""Routes Paystack webhook events to the appropriate service methods."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.repositories.db_revenue import DbRevenueRepository
from app.services.entitlement_service import EntitlementService
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

# Maps Paystack plan intervals to our period_months values.
_INTERVAL_TO_MONTHS: dict[str, int] = {
    "monthly": 1,
    "quarterly": 3,
    "biannually": 6,
    "annually": 12,
}

# Maps our period_months values to Paystack plan intervals.
_MONTHS_TO_INTERVAL: dict[int, str] = {
    v: k for k, v in _INTERVAL_TO_MONTHS.items()
}


class WebhookService:
    """Dispatches incoming Paystack events to service-layer handlers."""

    def __init__(self, repo: DbRevenueRepository) -> None:
        """
        Wire up the repository and downstream services.

        Args:
            repo: Shared db-service HTTP repository.
        """
        self.repo = repo
        self._paystack = PaystackClient(
            secret_key=settings.PAYSTACK_SECRET_KEY
        )
        self._sub_svc = SubscriptionService(
            repo, paystack_client=self._paystack
        )
        self._ent_svc = EntitlementService(repo)

    async def process_event(
        self, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """
        Dispatch a Paystack event to the matching handler.

        Unrecognised event types are logged and ignored — Paystack always
        receives a 200 regardless of whether we handle the event.

        Args:
            event_type: Paystack event string (e.g. ``charge.success``).
            event_data: The ``data`` payload from the Paystack event body.
        """
        handlers = {
            "charge.success": self._handle_charge_success,
            "subscription.create": self._handle_subscription_create,
            "subscription.disable": self._handle_subscription_disable,
            "invoice.payment_failed": self._handle_invoice_failed,
            "refund.processed": self._handle_refund,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(event_data)
        else:
            logger.info(
                "Unhandled Paystack event type=%s — skipping", event_type
            )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _setup_recurring_billing(
        self,
        *,
        estate_id: str,
        subscription_id: str,
        period_months: int,
        amount_kobo: int,
        currency: str,
        tier_slug: str,
        covered_users: int,
        period_end: str,
        authorization_code: str,
        customer_email: str,
    ) -> None:
        """
        Create a Paystack Plan + Subscription after the first payment and
        store the subscription_code on the estate subscription row.

        Failures are logged but do not propagate — the estate subscription
        is already active by the time this is called.
        """
        interval = _MONTHS_TO_INTERVAL.get(period_months, "monthly")
        plan_name = (
            f"GatePass {tier_slug} - {covered_users} seats - {interval}"
        )
        try:
            plan_data = await self._paystack.create_plan(
                name=plan_name,
                amount_kobo=amount_kobo,
                interval=interval,
                currency=currency,
            )
            plan_code: str = plan_data["plan_code"]

            sub_data = await self._paystack.create_subscription(
                customer_email=customer_email,
                plan_code=plan_code,
                authorization_code=authorization_code,
                start_date=period_end,
            )
            subscription_code: str = sub_data["subscription_code"]

            await self.repo.update_estate_subscription(
                subscription_id,
                {"paystack_subscription_code": subscription_code},
            )
            logger.info(
                "Recurring billing set up estate_id=%s "
                "subscription_id=%s subscription_code=%s plan_code=%s",
                estate_id,
                subscription_id,
                subscription_code,
                plan_code,
            )
        except Exception:
            logger.exception(
                "Failed to set up recurring billing estate_id=%s "
                "subscription_id=%s — subscription is active but "
                "auto-renew will not work until this is resolved",
                estate_id,
                subscription_id,
            )

    async def _update_plan_for_seat_add(
        self,
        *,
        estate_id: str,
        subscription_id: str,
        paystack_subscription_code: str,
        seats_added: int,
        new_covered_users: int,
        pricing_snapshot: dict,
    ) -> None:
        """
        Update the Paystack plan amount after a seat addition so that
        the next auto-renewal charges for the new seat count.

        Uses the proration pricing_snapshot to compute the per-seat
        delta; adds it to the current plan amount fetched from Paystack.

        Failures are logged but do not propagate — the DB is already
        updated and the proration charge has been collected.
        """
        try:
            # 1. Fetch Paystack subscription to get plan_code + amount.
            sub_data = await self._paystack.get_subscription(
                paystack_subscription_code
            )
            plan = sub_data.get("plan") or {}
            plan_code: str = plan.get("plan_code", "")
            if not plan_code:
                logger.error(
                    "seat_add: Paystack subscription missing plan_code "
                    "estate_id=%s subscription_code=%s",
                    estate_id,
                    paystack_subscription_code,
                )
                return

            old_amount_kobo: int = int(plan.get("amount") or 0)
            interval: str = plan.get("interval", "monthly")

            # 2. Compute seat delta from the proration pricing snapshot.
            #    price_per_seat is per seat per month; period_months is
            #    the subscription billing cadence inferred from the
            #    active subscription window at proration time.
            price_per_seat = Decimal(
                str(pricing_snapshot.get("price_per_seat") or 0)
            )
            period_months = int(pricing_snapshot.get("period_months") or 1)
            delta_kobo = int(
                price_per_seat * period_months * seats_added * 100
            )
            new_amount_kobo = old_amount_kobo + delta_kobo

            # 3. Update the Paystack plan.
            new_name = f"GatePass - {new_covered_users} seats - {interval}"
            await self._paystack.update_plan(
                plan_code,
                amount_kobo=new_amount_kobo,
                name=new_name,
            )
            logger.info(
                "seat_add: updated Paystack plan estate_id=%s "
                "plan_code=%s old_amount_kobo=%s new_amount_kobo=%s "
                "new_covered_users=%s",
                estate_id,
                plan_code,
                old_amount_kobo,
                new_amount_kobo,
                new_covered_users,
            )
        except Exception:
            logger.exception(
                "seat_add: failed to update Paystack plan "
                "estate_id=%s subscription_id=%s "
                "subscription_code=%s — DB is updated but "
                "auto-renewal amount will remain unchanged",
                estate_id,
                subscription_id,
                paystack_subscription_code,
            )

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #

    async def _handle_charge_success(self, data: dict[str, Any]) -> None:
        reference = data.get("reference", "")
        session = await self.repo.get_checkout_session_by_reference(reference)

        if session:
            await self._handle_initial_charge(data, session)
        else:
            await self._handle_renewal_charge(data)

    async def _handle_initial_charge(
        self, data: dict[str, Any], session: dict[str, Any]
    ) -> None:
        """Handle charge.success for a payment initiated via our checkout."""
        reference = data.get("reference", "")

        if session["status"] == "paid":
            logger.info(
                "charge.success replay reference=%s — already paid",
                reference,
            )
            return

        paid_at = datetime.now(tz=timezone.utc)
        metadata: dict[str, Any] = session.get("session_metadata") or {}
        estate_id = str(session["estate_id"])
        kind = session["checkout_kind"]

        await self.repo.create_payment_transaction(
            {
                "estate_id": estate_id,
                "checkout_session_id": str(session["id"]),
                "amount": str(session["amount"]),
                "currency_code": session["currency_code"],
                "status": "success",
                "provider_reference": reference,
                "raw": data,
            }
        )

        # Route by checkout_kind — mark session paid AFTER the service
        # call succeeds so a failed activation leaves the session unpaid
        # (allowing a retry or manual investigation).
        if kind in ("tier", "custom"):
            result = await self._sub_svc.activate(
                {
                    "estate_id": estate_id,
                    "tier_slug": metadata["tier_slug"],
                    "covered_users": metadata["covered_users"],
                    "period_months": metadata["period_months"],
                    "entitlements": metadata.get("entitlements"),
                    "ai_feature_keys": (metadata.get("ai_feature_keys") or []),
                    "paid_at": paid_at.isoformat(),
                }
            )

            await self.repo.update_checkout_session(
                str(session["id"]),
                {"status": "paid", "paid_at": paid_at.isoformat()},
            )

            # Set up recurring billing via Paystack Plan + Subscription.
            authorization_code = (data.get("authorization") or {}).get(
                "authorization_code", ""
            )
            customer_email = (data.get("customer") or {}).get("email", "")
            is_reusable = (data.get("authorization") or {}).get(
                "reusable", False
            )

            if authorization_code and customer_email:
                if not is_reusable:
                    # Card is not reusable — recurring billing cannot be
                    # set up. Mark auto_renew=False so the estate admin
                    # knows manual renewal will be required.
                    logger.warning(
                        "charge.success authorization not reusable — "
                        "skipping recurring billing, marking "
                        "auto_renew=False estate_id=%s reference=%s",
                        estate_id,
                        reference,
                    )
                    await self.repo.update_estate_subscription(
                        result["subscription_id"],
                        {"auto_renew": False},
                    )
                else:
                    amount_kobo = int(Decimal(str(session["amount"])) * 100)
                    await self._setup_recurring_billing(
                        estate_id=estate_id,
                        subscription_id=result["subscription_id"],
                        period_months=int(metadata["period_months"]),
                        amount_kobo=amount_kobo,
                        currency=session["currency_code"],
                        tier_slug=metadata["tier_slug"],
                        covered_users=int(metadata["covered_users"]),
                        period_end=result["period_end"],
                        authorization_code=authorization_code,
                        customer_email=customer_email,
                    )
            else:
                logger.warning(
                    "charge.success missing authorization_code or "
                    "customer email — recurring billing not set up "
                    "estate_id=%s reference=%s",
                    estate_id,
                    reference,
                )

        elif kind == "seat_add":
            seats_added = metadata.get("seats_added", 0)
            result = await self._sub_svc.apply_seat_add(estate_id, seats_added)
            await self.repo.update_checkout_session(
                str(session["id"]),
                {"status": "paid", "paid_at": paid_at.isoformat()},
            )
            # Update the Paystack plan amount so the next auto-renewal
            # charges for the new seat count, not the original.
            sub_code = (result.get("subscription") or {}).get(
                "paystack_subscription_code"
            )
            if sub_code:
                await self._update_plan_for_seat_add(
                    estate_id=estate_id,
                    subscription_id=str(result["subscription"]["id"]),
                    paystack_subscription_code=sub_code,
                    seats_added=seats_added,
                    new_covered_users=result["covered_users"],
                    pricing_snapshot=(session.get("pricing_snapshot") or {}),
                )
            else:
                logger.warning(
                    "seat_add: no paystack_subscription_code on "
                    "estate_id=%s — Paystack plan not updated; "
                    "auto-renewal amount will remain unchanged",
                    estate_id,
                )

        elif kind == "ai_only":
            await self._ent_svc.activate_ai_features(
                {
                    "estate_id": estate_id,
                    "ai_feature_keys": (metadata.get("ai_feature_keys") or []),
                    "period_months": metadata.get("period_months", 1),
                    "paid_at": paid_at.isoformat(),
                }
            )
            await self.repo.update_checkout_session(
                str(session["id"]),
                {"status": "paid", "paid_at": paid_at.isoformat()},
            )

    async def _handle_renewal_charge(self, data: dict[str, Any]) -> None:
        """
        Handle charge.success fired by Paystack for an auto-renewal.

        These events have no matching payment_checkout_session — they are
        identified via the subscription_code embedded in the event data.
        """
        reference = data.get("reference", "")
        paystack_sub_code = (data.get("subscription") or {}).get(
            "subscription_code", ""
        )

        if not paystack_sub_code:
            logger.warning(
                "charge.success reference=%s has no matching checkout "
                "session and no subscription_code — skipping",
                reference,
            )
            return

        subscription = (
            await self.repo.get_subscription_by_paystack_subscription_code(
                paystack_sub_code
            )
        )
        if not subscription:
            logger.warning(
                "charge.success auto-renewal: subscription_code=%s not "
                "linked to any estate — skipping",
                paystack_sub_code,
            )
            return

        estate_id = str(subscription["estate_id"])
        paid_at = datetime.now(tz=timezone.utc)

        interval = (data.get("plan") or {}).get("interval", "monthly")
        period_months = _INTERVAL_TO_MONTHS.get(interval)
        if period_months is None:
            logger.warning(
                "charge.success renewal has unrecognised plan interval=%r — "
                "defaulting to 1 month. Review paystack_subscription_code=%s",
                interval,
                paystack_sub_code,
            )
            period_months = 1

        await self.repo.create_payment_transaction(
            {
                "estate_id": estate_id,
                "checkout_session_id": None,
                "amount": str(data.get("amount", 0) / 100),
                # Prefer currency from the event; fall back to subscription row.
                "currency_code": (
                    data.get("currency")
                    or subscription.get("currency_code", "NGN")
                ),
                "status": "success",
                "provider_reference": reference,
                "raw": data,
            }
        )

        await self._sub_svc.renew(
            estate_id,
            period_months=period_months,
            paid_at=paid_at,
        )
        logger.info(
            "Auto-renewal processed estate_id=%s reference=%s "
            "period_months=%s",
            estate_id,
            reference,
            period_months,
        )

    async def _handle_subscription_create(self, data: dict[str, Any]) -> None:
        """
        Confirmation that Paystack created the recurring subscription.

        The subscription_code is already stored directly from the API
        response in _setup_recurring_billing. This handler persists the
        paystack_customer_code as a backup in case the API write failed.
        """
        subscription_code = data.get("subscription_code")
        customer_code = (data.get("customer") or {}).get("customer_code")
        logger.info(
            "subscription.create confirmed subscription_code=%s "
            "customer_code=%s",
            subscription_code,
            customer_code,
        )

        if subscription_code and customer_code:
            subscription = (
                await self.repo.get_subscription_by_paystack_subscription_code(
                    subscription_code
                )
            )
            if subscription:
                await self.repo.update_estate_subscription(
                    str(subscription["id"]),
                    {"paystack_customer_code": customer_code},
                )
            else:
                logger.warning(
                    "subscription.create: subscription_code=%s not linked "
                    "to any estate — paystack_customer_code not stored",
                    subscription_code,
                )

    async def _handle_subscription_disable(self, data: dict[str, Any]) -> None:
        """
        Paystack subscription was disabled — mark auto_renew=false on our
        side (does not change period_end; access continues until expiry).
        """
        subscription_code = data.get("subscription_code", "")
        if not subscription_code:
            logger.warning(
                "subscription.disable missing subscription_code — skipping"
            )
            return

        subscription = (
            await self.repo.get_subscription_by_paystack_subscription_code(
                subscription_code
            )
        )
        if not subscription:
            logger.warning(
                "subscription.disable subscription_code=%s not linked "
                "to any estate — skipping",
                subscription_code,
            )
            return

        estate_id = str(subscription["estate_id"])
        # call_paystack=False: Paystack already disabled the subscription
        # on their side — no need to call the API again.
        await self._sub_svc.cancel(estate_id, call_paystack=False)
        logger.info(
            "subscription.disable: cancelled auto_renew for "
            "estate_id=%s subscription_code=%s",
            estate_id,
            subscription_code,
        )

    async def _handle_invoice_failed(self, data: dict[str, Any]) -> None:
        """
        Set an estate subscription to ``past_due`` when a payment fails
        mid-cycle (i.e. before the subscription's period_end).

        Failures that arrive after period_end (grace-window retries) are
        logged but do NOT change the subscription status.
        """
        # TODO: Integrate the notification service to send payment failure
        # emails to the estate admin. Paystack may send its own receipts
        # via dashboard email settings — verify before adding our own to
        # avoid duplicate notifications.

        # Auto-renewal invoice failures carry a subscription_code; use it
        # as the primary lookup. Initial-payment failures have no
        # subscription_code — fall back to the GP- reference.
        paystack_sub_code = (data.get("subscription") or {}).get(
            "subscription_code", ""
        )

        if paystack_sub_code:
            subscription = (
                await self.repo.get_subscription_by_paystack_subscription_code(
                    paystack_sub_code
                )
            )
            if not subscription:
                logger.warning(
                    "invoice.payment_failed subscription_code=%s not "
                    "linked to any estate — skipping",
                    paystack_sub_code,
                )
                return
            estate_id = str(subscription["estate_id"])
        else:
            reference = data.get("reference", "")
            session = await self.repo.get_checkout_session_by_reference(
                reference
            )
            if not session:
                logger.warning(
                    "invoice.payment_failed for unknown reference=%s",
                    reference,
                )
                return
            estate_id = str(session["estate_id"])
            subscription = await self.repo.get_active_subscription(estate_id)
            if not subscription:
                logger.warning(
                    "invoice.payment_failed: no active subscription for "
                    "estate_id=%s reference=%s",
                    estate_id,
                    reference,
                )
                return

        period_end_raw = subscription.get("period_end")
        if not period_end_raw:
            return

        period_end = datetime.fromisoformat(
            str(period_end_raw).replace("Z", "+00:00")
        )
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)

        now = datetime.now(tz=timezone.utc)
        if now < period_end:
            await self.repo.update_estate_subscription(
                str(subscription["id"]), {"status": "past_due"}
            )
            logger.info(
                "invoice.payment_failed mid-cycle: set past_due "
                "estate_id=%s subscription_id=%s",
                estate_id,
                subscription["id"],
            )
        else:
            logger.info(
                "invoice.payment_failed in grace window — no status change "
                "estate_id=%s subscription_id=%s",
                estate_id,
                subscription["id"],
            )

    async def _handle_refund(self, data: dict[str, Any]) -> None:
        reference = data.get("reference") or data.get(
            "transaction_reference", ""
        )
        session = await self.repo.get_checkout_session_by_reference(reference)
        if not session:
            logger.warning(
                "refund.processed reference=%s has no matching checkout "
                "session — skipping ledger entry",
                reference,
            )
            return

        amount = data.get("amount", 0)
        await self.repo.create_payment_transaction(
            {
                "estate_id": str(session["estate_id"]),
                "checkout_session_id": str(session["id"]),
                "amount": str(amount / 100),  # kobo → major unit
                "currency_code": session["currency_code"],
                "status": "refund",
                "provider_reference": reference,
                "raw": data,
            }
        )
        logger.info(
            "refund.processed reference=%s amount=%s", reference, amount
        )
