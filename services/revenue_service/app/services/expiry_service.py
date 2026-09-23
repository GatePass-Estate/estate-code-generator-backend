"""Daily cron: expire stale subscriptions and AI grants."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.notify import fire_notify
from app.repositories.db_revenue import DbRevenueRepository

logger = logging.getLogger(__name__)


class ExpiryService:
    def __init__(
        self,
        repo: DbRevenueRepository,
        paystack: PaystackClient,
    ) -> None:
        self.repo = repo
        self._paystack = paystack

    async def run(self) -> dict:
        n_subs = await self._expire_subscriptions()
        n_grants = await self._expire_ai_grants()
        return {"expired_subscriptions": n_subs, "expired_ai_grants": n_grants}

    async def _expire_subscriptions(self) -> int:
        now = datetime.now(tz=timezone.utc)
        grace_cutoff = now - timedelta(days=settings.RENEWAL_GRACE_PERIOD_DAYS)

        # Fetch all active/trialing whose period has ended (period_end < now).
        # Split in Python: in_grace vs past_grace.
        all_ended_active = await self.repo.search_subscriptions(
            statuses=["active", "trialing"],
            period_end_before=now.isoformat(),
        )

        in_grace: list[dict] = []
        past_grace: list[dict] = []
        for sub in all_ended_active:
            period_end = _parse_dt(sub.get("period_end", ""))
            if period_end is not None and period_end >= grace_cutoff:
                in_grace.append(sub)
            else:
                past_grace.append(sub)

        # past_due/cancelled: no grace, expire immediately
        immediate = await self.repo.search_subscriptions(
            statuses=["past_due", "cancelled"],
            period_end_before=now.isoformat(),
        )

        access_tier = await self.repo.get_tier_by_slug("access")
        max_users = ((access_tier or {}).get("entitlements") or {}).get(
            "max_active_users", 0
        )

        # In-grace: warn only, do not expire
        for sub in in_grace:
            await _notify_grace_warning(sub["estate_id"])

        # Past grace: disable Paystack + expire + notify
        count = 0
        for sub in past_grace:
            sub_code = sub.get("paystack_subscription_code")
            if sub_code:
                try:
                    await self._paystack.disable_subscription(sub_code)
                except Exception:
                    logger.exception(
                        "Cron: failed to disable Paystack subscription "
                        "subscription_code=%s estate_id=%s — expiring anyway",
                        sub_code,
                        sub.get("estate_id"),
                    )
            await self._expire_one(sub, max_users)
            await _notify_subscription_expired(sub["estate_id"])
            count += 1

        # Immediate: expire + notify (Paystack already handled by webhook)
        for sub in immediate:
            await self._expire_one(sub, max_users)
            await _notify_subscription_expired(sub["estate_id"])
            count += 1

        return count

    async def _expire_one(self, sub: dict, max_users: int) -> None:
        """Patch status=expired and set over_cap_locked if needed."""
        sub_id = str(sub["id"])
        await self.repo.update_estate_subscription(
            sub_id, {"status": "expired"}
        )
        estate_id = str(sub["estate_id"])
        active_count = await self.repo.get_estate_active_user_count(estate_id)
        if active_count > max_users:
            await self.repo.update_estate_subscription(
                sub_id, {"over_cap_locked": True}
            )

    async def _expire_ai_grants(self) -> int:
        now = datetime.now(tz=timezone.utc)
        grace_cutoff = (
            now - timedelta(days=settings.RENEWAL_GRACE_PERIOD_DAYS)
        ).isoformat()

        grants = await self.repo.search_ai_grants(
            status="active",
            is_free=False,
            expires_at_before=grace_cutoff,
        )
        for grant in grants:
            await self.repo.update_estate_ai_feature(
                str(grant["id"]),
                {"status": "expired", "is_installed": False},
            )

        return len(grants)


def _parse_dt(value: str) -> datetime | None:
    """Parse an ISO datetime string; return None if blank or invalid."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


async def _notify_grace_warning(estate_id: str) -> None:
    """Email + in-app to primary_admin; in-app only to admins: grace period."""
    estate_id = str(estate_id)
    # Email + in-app → primary_admin (type is in EMAIL_TYPES + PUSH_TYPES)
    await fire_notify(
        {
            "type": "SUBSCRIPTION_GRACE_PERIOD",
            "title": "Subscription payment overdue",
            "body": (
                "Your subscription payment is overdue. "
                "Please renew within the grace period to avoid losing access."
            ),
            "fan_out": {"estate_id": estate_id, "roles": ["primary_admin"]},
            "metadata": {"estate_id": estate_id},
        }
    )
    # In-app only → regular admins (type is in PUSH_TYPES only, not EMAIL_TYPES)
    await fire_notify(
        {
            "type": "SUBSCRIPTION_GRACE_PERIOD_ADMIN",
            "title": "Subscription payment overdue",
            "body": (
                "Your estate subscription payment is overdue. "
                "Contact your primary admin to renew."
            ),
            "fan_out": {"estate_id": estate_id, "roles": ["admin"]},
            "metadata": {"estate_id": estate_id},
        }
    )


async def _notify_subscription_expired(estate_id: str) -> None:
    """Email + in-app to primary_admin only: subscription expired."""
    estate_id = str(estate_id)
    await fire_notify(
        {
            "type": "SUBSCRIPTION_EXPIRED",
            "title": "Subscription expired",
            "body": (
                "Your estate subscription has expired. "
                "Renew now to restore full access for your community."
            ),
            "fan_out": {"estate_id": estate_id, "roles": ["primary_admin"]},
            "metadata": {"estate_id": estate_id},
        }
    )
