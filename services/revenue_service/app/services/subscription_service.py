"""Estate subscription lookups."""

from __future__ import annotations

from app.repositories.db_revenue import DbRevenueRepository
from app.services.entitlement_resolver import resolve_entitlements


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

        Args:
            estate_id: Estate UUID string.

        Returns:
            Payload with subscription, tier, and effective_entitlements.
        """
        access_tier = await self.repo.get_tier_by_slug("access")
        subscription = await self.repo.get_active_subscription(estate_id)
        tier = None
        if subscription:
            tier = await self.repo.get_tier_by_id(str(subscription["tier_id"]))
        entitlements = resolve_entitlements(
            subscription=subscription,
            tier=tier,
            access_tier=access_tier or {"entitlements": {}},
        )
        return {
            "estate_id": estate_id,
            "subscription": subscription,
            "tier": tier,
            "effective_entitlements": entitlements,
        }
