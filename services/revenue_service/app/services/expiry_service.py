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
        await self._pre_expiry_warnings()
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
        if not access_tier:
            logger.critical(
                "Access tier not seeded — skipping subscription expiry "
                "to avoid leaving estates with no active subscription. "
                "Seed the access tier and re-run."
            )
            return 0
        max_users = int(
            (access_tier.get("entitlements") or {}).get("max_active_users", 0)
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
            try:
                await self._expire_one(sub, access_tier, max_users)
                await _notify_subscription_expired(sub["estate_id"])
                count += 1
            except Exception:
                logger.exception(
                    "Cron: failed to expire subscription "
                    "sub_id=%s estate_id=%s — skipping",
                    sub.get("id"),
                    sub.get("estate_id"),
                )

        # Immediate: expire + notify (Paystack already handled by webhook)
        for sub in immediate:
            try:
                await self._expire_one(sub, access_tier, max_users)
                await _notify_subscription_expired(sub["estate_id"])
                count += 1
            except Exception:
                logger.exception(
                    "Cron: failed to expire subscription "
                    "sub_id=%s estate_id=%s — skipping",
                    sub.get("id"),
                    sub.get("estate_id"),
                )

        return count

    async def _expire_one(
        self, sub: dict, access_tier: dict, max_users: int
    ) -> None:
        """Mark the paid subscription expired and create a new access row.

        The expired row is kept intact as a historical record (original
        tier_id, period_start, and period_end are preserved). A new active
        access-tier subscription is created so the estate always has an
        explicit row on record. over_cap_locked is set on the new row when
        active users exceed the access seat cap.

        If the access row creation fails, the paid row is restored to its
        prior status so the estate is not left with no active subscription.
        """
        sub_id = str(sub["id"])
        estate_id = str(sub["estate_id"])
        prior_status = (sub.get("status") or "active").lower()

        # Preserve the original row as history — only flip the status.
        await self.repo.update_estate_subscription(
            sub_id, {"status": "expired"}
        )

        active_count = await self.repo.get_estate_active_user_count(estate_id)
        over_cap = active_count > max_users
        now = datetime.now(tz=timezone.utc)
        try:
            await self.repo.create_estate_subscription(
                {
                    "estate_id": estate_id,
                    "tier_id": access_tier["id"],
                    "status": "active",
                    "period_start": now.isoformat(),
                    "period_end": None,
                    "auto_renew": False,
                    "covered_users": max_users or 1,
                    "entitlements": None,
                    "cancelled_at": None,
                    "pending_tier_slug": None,
                    "pending_covered_users": None,
                    "over_cap_locked": over_cap,
                }
            )
        except Exception:
            logger.exception(
                "Failed to create access subscription after expiry "
                "estate_id=%s — restoring prior status=%s to avoid "
                "leaving estate with no active subscription",
                estate_id,
                prior_status,
            )
            await self.repo.update_estate_subscription(
                sub_id, {"status": prior_status}
            )
            raise
        logger.info(
            "Created access subscription after expiry estate_id=%s "
            "over_cap_locked=%s active_count=%s max_users=%s",
            estate_id,
            over_cap,
            active_count,
            max_users,
        )

    async def _expire_ai_grants(self) -> int:
        now = datetime.now(tz=timezone.utc)
        grace_cutoff = now - timedelta(days=settings.RENEWAL_GRACE_PERIOD_DAYS)
        now_iso = now.isoformat()
        # Pass A — active grants whose expires_at < now
        all_active_expired = await self.repo.search_ai_grants(
            status="active",
            is_free=False,
            expires_at_before=now_iso,
        )
        in_grace: list[dict] = []
        past_grace: list[dict] = []
        for grant in all_active_expired:
            expires_at = _parse_dt(str(grant.get("expires_at") or ""))
            if expires_at is not None and expires_at >= grace_cutoff:
                in_grace.append(grant)
            else:
                past_grace.append(grant)

        for grant in in_grace:
            await _notify_ai_grant_grace(grant)

        count = 0
        for grant in past_grace:
            await self.repo.update_estate_ai_feature(
                str(grant["id"]),
                {"status": "expired", "is_installed": False},
            )
            await _notify_ai_grant_expired(grant)
            count += 1

        # Pass B — stale cleanup: cancelled/past_due past their expires_at.
        # No grace for these statuses — expire as soon as expires_at passes.
        stale = await self.repo.search_stale_ai_grants(
            expires_at_before=now_iso,
        )
        for grant in stale:
            await self.repo.update_estate_ai_feature(
                str(grant["id"]),
                {"status": "expired", "is_installed": False},
            )
            count += 1

        return count

    async def _pre_expiry_warnings(self) -> None:
        now = datetime.now(tz=timezone.utc)
        warning_cutoff = now + timedelta(days=settings.PRE_EXPIRY_WARNING_DAYS)
        now_iso = now.isoformat()
        warning_cutoff_iso = warning_cutoff.isoformat()

        # Estate subscriptions approaching period_end
        subs = await self.repo.search_subscriptions_pre_expiry(
            period_end_before=warning_cutoff_iso,
            period_end_after=now_iso,
        )
        for sub in subs:
            auto_renew = bool(sub.get("auto_renew"))
            period_end = _parse_dt(str(sub.get("period_end") or ""))
            period_end_str = (
                period_end.strftime("%d %b %Y") if period_end else "soon"
            )
            estate_id = str(sub["estate_id"])
            if auto_renew:
                title = "Subscription renewing soon"
                body = (
                    f"Your estate subscription will automatically renew "
                    f"on {period_end_str}. No action is needed — "
                    f"we'll handle the rest."
                )
            else:
                title = "Subscription expiring soon"
                body = (
                    f"Your estate subscription expires on "
                    f"{period_end_str}. Renew before this date to avoid "
                    f"losing access to your estate's features."
                )
            await fire_notify(
                {
                    "type": "SUBSCRIPTION_RENEWAL_REMINDER",
                    "title": title,
                    "body": body,
                    "fan_out": {
                        "estate_id": estate_id,
                        "roles": ["primary_admin"],
                    },
                    "metadata": {"estate_id": estate_id},
                }
            )
            await self.repo.update_estate_subscription(
                str(sub["id"]), {"pre_expiry_notified": True}
            )

        # Standalone AI grants approaching expires_at
        grants = await self.repo.search_ai_grants_pre_expiry(
            expires_at_before=warning_cutoff_iso,
            expires_at_after=now_iso,
        )
        for grant in grants:
            auto_renew = bool(grant.get("auto_renew"))
            expires_at = _parse_dt(str(grant.get("expires_at") or ""))
            expires_str = (
                expires_at.strftime("%d %b %Y") if expires_at else "soon"
            )
            estate_id = str(grant["estate_id"])
            if auto_renew:
                title = "AI feature renewing soon"
                body = (
                    f"Your AI feature subscription will automatically "
                    f"renew on {expires_str}. No action needed."
                )
            else:
                title = "AI feature expiring soon"
                body = (
                    f"Your access to this AI feature expires on "
                    f"{expires_str}. Renew before this date to keep the "
                    f"feature active for your estate."
                )
            await fire_notify(
                {
                    "type": "AI_GRANT_RENEWAL_REMINDER",
                    "title": title,
                    "body": body,
                    "fan_out": {
                        "estate_id": estate_id,
                        "roles": ["primary_admin"],
                    },
                    "metadata": {"estate_id": estate_id},
                }
            )
            await self.repo.update_estate_ai_feature(
                str(grant["id"]), {"pre_expiry_notified": True}
            )


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
    # In-app only → regular admins (PUSH_TYPES only, not EMAIL_TYPES)
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


async def _notify_ai_grant_grace(grant: dict) -> None:
    """Push + in-app to primary_admin: AI grant in grace period."""
    estate_id = str(grant["estate_id"])
    await fire_notify(
        {
            "type": "AI_GRANT_GRACE_PERIOD",
            "title": "AI feature payment overdue",
            "body": (
                "Your AI feature payment is overdue. Please renew "
                "within the grace period to avoid losing access."
            ),
            "fan_out": {
                "estate_id": estate_id,
                "roles": ["primary_admin"],
            },
            "metadata": {"estate_id": estate_id},
        }
    )
    await fire_notify(
        {
            "type": "AI_GRANT_GRACE_PERIOD_ADMIN",
            "title": "AI feature payment overdue",
            "body": (
                "Your estate's AI feature payment is overdue. "
                "Contact your primary admin to renew."
            ),
            "fan_out": {"estate_id": estate_id, "roles": ["admin"]},
            "metadata": {"estate_id": estate_id},
        }
    )


async def _notify_ai_grant_expired(grant: dict) -> None:
    """Email + in-app to primary_admin: AI grant expired."""
    estate_id = str(grant["estate_id"])
    await fire_notify(
        {
            "type": "AI_GRANT_EXPIRED",
            "title": "AI feature access expired",
            "body": (
                "Your AI feature access has expired. Renew now to "
                "restore the feature for your estate."
            ),
            "fan_out": {
                "estate_id": estate_id,
                "roles": ["primary_admin"],
            },
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
