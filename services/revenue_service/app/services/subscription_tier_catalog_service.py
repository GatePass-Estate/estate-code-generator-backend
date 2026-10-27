"""Read subscription tier catalog from db-service for external clients."""

from __future__ import annotations

from fastapi import HTTPException

from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.subscription_tiers import (
    SubscriptionTierCatalogItem,
    SubscriptionTierListResponse,
)


class SubscriptionTierCatalogService:
    def __init__(self, repo: DbRevenueRepository) -> None:
        self._repo = repo

    @staticmethod
    def _item(raw: dict) -> SubscriptionTierCatalogItem:
        return SubscriptionTierCatalogItem.model_validate(raw)

    async def list_tiers(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        is_active: bool | None = True,
    ) -> SubscriptionTierListResponse:
        if is_active is None:
            body = await self._repo.list_subscription_tiers(
                page=page, limit=limit
            )
        else:
            body = await self._repo.search_subscription_tiers(
                is_active=is_active,
                page=page,
                limit=limit,
            )
        items = [self._item(row) for row in body.get("items") or []]
        return SubscriptionTierListResponse(
            items=items,
            total=body.get("total"),
            page=int(body.get("page") or page),
            limit=int(body.get("limit") or limit),
        )

    async def get_tier_by_id(
        self, tier_id: str
    ) -> SubscriptionTierCatalogItem:
        raw = await self._repo.get_tier_by_id(tier_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Tier not found")
        return self._item(raw)

    async def get_my_tier(
        self, estate_id: str | None
    ) -> SubscriptionTierCatalogItem | None:
        """Return the tier for the caller's active subscription, or None."""
        if not estate_id:
            return None
        sub = await self._repo.get_active_subscription(estate_id)
        if not sub or sub.get("status") not in (
            "active",
            "trialing",
            "cancelled",
        ):
            return None
        tier_id = str(sub.get("tier_id") or "")
        if not tier_id:
            return None
        raw = await self._repo.get_tier_by_id(tier_id)
        if not raw:
            return None
        return self._item(raw)

    async def get_tier_by_slug(self, slug: str) -> SubscriptionTierCatalogItem:
        raw = await self._repo.get_tier_by_slug(slug)
        if not raw:
            raise HTTPException(status_code=404, detail="Tier not found")
        return self._item(raw)
