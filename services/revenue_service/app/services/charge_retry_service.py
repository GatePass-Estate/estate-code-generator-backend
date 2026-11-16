"""Self-managed charge retry processor.

Processes pending retry schedules created by the webhook handler when
Paystack's auto-renewal charge fails.  Each due retry attempts a
``charge_authorization`` call and, on success, renews the subscription
or extends the AI grant — mirroring the existing renewal webhook flow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.notify import fire_notify
from app.libs.period_dating import compute_period_end
from app.repositories.db_revenue import DbRevenueRepository
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

# Maps Paystack plan intervals to our period_months values.
_INTERVAL_TO_MONTHS: dict[str, int] = {
    "monthly": 1,
    "quarterly": 3,
    "biannually": 6,
    "annually": 12,
}


def _parse_retry_schedule() -> list[int]:
    """Parse CHARGE_RETRY_INTERVALS_HOURS into a list of hour offsets."""
    raw = settings.CHARGE_RETRY_INTERVALS_HOURS
    return [int(h.strip()) for h in raw.split(",") if h.strip()]


class ChargeRetryService:
    """Processes pending charge retries.  Instantiated per cron invocation."""

    def __init__(
        self,
        repo: DbRevenueRepository,
        paystack: PaystackClient,
    ) -> None:
        self.repo = repo
        self._paystack = paystack
        self._sub_svc = SubscriptionService(repo, paystack_client=paystack)

    async def run(self) -> dict[str, int]:
        """
        Cron entry point.  Finds all pending retries that are due and
        attempts a charge for each.

        Returns:
            Counts of attempted / succeeded / failed retries.
        """
        now = datetime.now(tz=timezone.utc)
        due = await self.repo.search_pending_retries_due(now.isoformat())
        results = {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
        }
        for retry in due:
            try:
                await self._process_one(retry, now, results)
            except Exception:
                logger.exception(
                    "Unhandled error processing retry id=%s",
                    retry.get("id"),
                )
                results["failed"] += 1
        return results

    async def _process_one(
        self,
        retry: dict[str, Any],
        now: datetime,
        results: dict[str, int],
    ) -> None:
        """Attempt a single charge retry."""
        retry_id = str(retry["id"])
        attempt = int(retry.get("attempt_number", 0)) + 1
        max_attempts = int(retry.get("max_attempts", 1))

        # Pre-check: if the target was already renewed (e.g. customer
        # paid manually or Paystack sent a late success), cancel.
        if await self._target_already_active(retry):
            await self.repo.update_payment_charge_retry(
                retry_id,
                {
                    "status": "cancelled",
                    "resolved_at": now.isoformat(),
                },
            )
            logger.info(
                "Retry id=%s cancelled — target already active", retry_id
            )
            return

        reference = f"GP-RETRY-{retry_id}-{attempt}"
        results["attempted"] += 1

        try:
            charge_data = await self._paystack.charge_authorization(
                authorization_code=retry["authorization_code"],
                email=retry["customer_email"],
                amount_kobo=int(retry["amount_kobo"]),
                reference=reference,
                currency=retry.get("currency_code", "NGN"),
            )
        except Exception:
            logger.exception(
                "charge_authorization network/envelope error retry_id=%s",
                retry_id,
            )
            # Treat as a temporary failure — advance to next retry slot.
            await self._advance_or_exhaust(
                retry,
                retry_id,
                attempt,
                max_attempts,
                now,
                gateway_response="network_error",
                provider_reference=reference,
            )
            results["failed"] += 1
            return

        charge_status = (charge_data.get("status") or "").lower()
        gateway_response = charge_data.get("gateway_response", "")

        if charge_status == "success":
            await self._on_success(retry, charge_data, now)
            await self.repo.update_payment_charge_retry(
                retry_id,
                {
                    "status": "succeeded",
                    "attempt_number": attempt,
                    "last_attempted_at": now.isoformat(),
                    "last_gateway_response": gateway_response,
                    "last_provider_reference": reference,
                    "resolved_at": now.isoformat(),
                },
            )
            results["succeeded"] += 1
            logger.info(
                "Charge retry succeeded retry_id=%s reference=%s",
                retry_id,
                reference,
            )
        else:
            await self._advance_or_exhaust(
                retry,
                retry_id,
                attempt,
                max_attempts,
                now,
                gateway_response=gateway_response,
                provider_reference=reference,
            )
            results["failed"] += 1
            logger.info(
                "Charge retry failed retry_id=%s attempt=%d/%d "
                "gateway_response=%s",
                retry_id,
                attempt,
                max_attempts,
                gateway_response,
            )

    async def _advance_or_exhaust(
        self,
        retry: dict[str, Any],
        retry_id: str,
        attempt: int,
        max_attempts: int,
        now: datetime,
        *,
        gateway_response: str,
        provider_reference: str,
    ) -> None:
        """Advance to the next retry slot or mark exhausted."""
        schedule = _parse_retry_schedule()

        patch: dict[str, Any] = {
            "attempt_number": attempt,
            "last_attempted_at": now.isoformat(),
            "last_gateway_response": gateway_response,
            "last_provider_reference": provider_reference,
        }

        if attempt >= max_attempts or attempt >= len(schedule):
            patch["status"] = "failed"
            patch["resolved_at"] = now.isoformat()
            patch["next_retry_at"] = None
            logger.info(
                "Retry exhausted retry_id=%s after %d attempts",
                retry_id,
                attempt,
            )
        else:
            # Schedule the next retry relative to when the retry was
            # originally created (not relative to now).
            created_at_raw = retry.get("created_at", "")
            try:
                created_at = datetime.fromisoformat(
                    str(created_at_raw).replace("Z", "+00:00")
                )
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                created_at = now

            next_hours = schedule[attempt]
            next_retry_at = created_at + timedelta(hours=next_hours)
            patch["next_retry_at"] = next_retry_at.isoformat()

        await self.repo.update_payment_charge_retry(retry_id, patch)

    async def _on_success(
        self,
        retry: dict[str, Any],
        charge_data: dict[str, Any],
        now: datetime,
    ) -> None:
        """Handle a successful charge retry — renew the target."""
        estate_id = str(retry["estate_id"])
        target_type = retry["target_type"]
        reference = charge_data.get("reference", "")
        amount = charge_data.get("amount", retry.get("amount_kobo", 0))
        currency = charge_data.get(
            "currency", retry.get("currency_code", "NGN")
        )

        # Record the payment transaction.
        await self.repo.create_payment_transaction(
            {
                "estate_id": estate_id,
                "checkout_session_id": None,
                "amount": amount,
                "currency_code": currency,
                "status": "success",
                "provider_reference": reference,
                "raw": charge_data,
            }
        )

        if target_type == "estate_subscription":
            await self._renew_subscription(retry, estate_id, now)
        elif target_type == "ai_grant":
            await self._extend_ai_grant(retry, estate_id, now)

        # Send success notification.
        notify_type = (
            "SUBSCRIPTION_RENEWAL_SUCCESS"
            if target_type == "estate_subscription"
            else "AI_GRANT_RENEWAL_SUCCESS"
        )
        await fire_notify(
            {
                "type": notify_type,
                "title": "Payment retry succeeded",
                "body": (
                    "A previously failed payment has been successfully "
                    "retried. Your access has been renewed."
                ),
                "fan_out": {
                    "estate_id": estate_id,
                    "roles": ["primary_admin"],
                },
                "metadata": {"estate_id": estate_id},
            }
        )

    async def _renew_subscription(
        self,
        retry: dict[str, Any],
        estate_id: str,
        now: datetime,
    ) -> None:
        """Renew an estate subscription after a successful retry charge."""
        # Determine period_months from the Paystack subscription's plan.
        sub_code = retry.get("paystack_subscription_code", "")
        period_months = 1
        if sub_code:
            try:
                sub_data = await self._paystack.fetch_subscription(sub_code)
                interval = (sub_data.get("plan") or {}).get(
                    "interval", "monthly"
                )
                period_months = _INTERVAL_TO_MONTHS.get(interval, 1)
            except Exception:
                logger.warning(
                    "Could not fetch subscription interval for %s — "
                    "defaulting to 1 month",
                    sub_code,
                )

        await self._sub_svc.renew(
            estate_id,
            period_months=period_months,
            paid_at=now,
        )

    async def _extend_ai_grant(
        self,
        retry: dict[str, Any],
        estate_id: str,
        now: datetime,
    ) -> None:
        """Extend an AI grant's expires_at after a successful retry charge."""
        grant_id = str(retry["target_id"])
        sub_code = retry.get("paystack_subscription_code", "")

        # Determine period_months from the Paystack subscription's plan.
        period_months = 1
        if sub_code:
            try:
                sub_data = await self._paystack.fetch_subscription(sub_code)
                interval = (sub_data.get("plan") or {}).get(
                    "interval", "monthly"
                )
                period_months = _INTERVAL_TO_MONTHS.get(interval, 1)
            except Exception:
                logger.warning(
                    "Could not fetch subscription interval for %s — "
                    "defaulting to 1 month",
                    sub_code,
                )

        # Fetch current grant to get old expires_at.
        grants = await self.repo.list_estate_ai_features(estate_id)
        ai_grant = next((g for g in grants if str(g["id"]) == grant_id), None)
        old_expires_at = None
        if ai_grant:
            raw = ai_grant.get("expires_at")
            if raw:
                try:
                    old_expires_at = datetime.fromisoformat(
                        str(raw).replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

        new_expires_at = compute_period_end(
            paid_at=now,
            duration=timedelta(days=30 * period_months),
            old_period_end=old_expires_at,
            grace_days=settings.RENEWAL_GRACE_PERIOD_DAYS,
        )

        await self.repo.update_estate_ai_feature(
            grant_id,
            {
                "status": "active",
                "is_installed": True,
                "expires_at": new_expires_at.isoformat(),
                "pre_expiry_notified": False,
            },
        )
        logger.info(
            "AI grant retry renewal grant_id=%s estate_id=%s "
            "new_expires_at=%s",
            grant_id,
            estate_id,
            new_expires_at.isoformat(),
        )

    async def _target_already_active(self, retry: dict[str, Any]) -> bool:
        """Check if the target subscription/grant has been renewed."""
        estate_id = str(retry["estate_id"])
        target_type = retry["target_type"]
        target_id = str(retry["target_id"])

        if target_type == "estate_subscription":
            sub = await self.repo.get_active_subscription(estate_id)
            if sub and str(sub["id"]) == target_id:
                return sub.get("status") == "active"
        elif target_type == "ai_grant":
            grants = await self.repo.list_estate_ai_features(estate_id)
            grant = next(
                (g for g in grants if str(g["id"]) == target_id), None
            )
            if grant:
                return grant.get("status") == "active"
        return False
