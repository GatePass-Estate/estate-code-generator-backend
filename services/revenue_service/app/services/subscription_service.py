"""Estate subscription lookups."""

from __future__ import annotations

from fastapi import HTTPException

from app.repositories.db_revenue import DbRevenueRepository
from app.services.entitlement_resolver import (
    ACTIVE_STATUSES,
    resolve_entitlements,
)


class SubscriptionService:
    """Reads estate subscriptions and resolves effective entitlements."""

    def __init__(self, repo: DbRevenueRepository):
        """
        Bind the db-service revenue repository.

        Args:
            repo: Repository used for subscription and tier lookups.
        """
        self.repo = repo

    async def get_estate_subscription(self, estate_id: str) -> dict:
        """
        Return subscription, tier, and effective entitlements for an estate.

        Resolves by estate subscription first. Loads the Access tier only
        when falling back (no subscription, inactive status, or missing tier).

        Args:
            estate_id: Estate UUID string.

        Returns:
            Payload with subscription, tier, and effective_entitlements.

        Raises:
            HTTPException: 500 if Access fallback is needed but not seeded.
        """
        subscription = await self.repo.get_active_subscription(estate_id)
        tier = None
        if subscription:
            tier = await self.repo.get_tier_by_id(str(subscription["tier_id"]))

        status = ((subscription or {}).get("status") or "").lower()
        needs_access_fallback = (
            not subscription or status not in ACTIVE_STATUSES or not tier
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
