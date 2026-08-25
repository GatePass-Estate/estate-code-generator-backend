"""HTTP repositories calling db-service revenue + estate APIs."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class DbRevenueRepository:
    """HTTP wrapper for db-service revenue and estate endpoints."""

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Bind endpoint base URLs from settings.

        Args:
            http_client: Shared async HTTP handler.
        """
        self.client = http_client
        base = settings.DB_SERVICE_URL.rstrip("/") + "/"
        self.base = base
        self.estates = f"{base}api/v1/userprofile/estates"
        self.service_catalog = f"{base}api/v1/revenue/servicecatalog"
        self.ai_feature = f"{base}api/v1/revenue/aifeature"
        self.feature_unit_price = f"{base}api/v1/revenue/featureunitprice"
        self.subscription_tier = f"{base}api/v1/revenue/subscriptiontier"
        self.estate_subscription = f"{base}api/v1/revenue/estatesubscription"
        self.estate_ai_feature = f"{base}api/v1/revenue/estateaifeature"

    async def _search(
        self, endpoint: str, params: dict[str, Any]
    ) -> list[dict]:
        """
        Call a db-service search endpoint and return items.

        Args:
            endpoint: Base resource URL (without /search).
            params: Query filters; None values are dropped.

        Returns:
            List of item dicts from the search response.

        Raises:
            HTTPException: 502 if the db-service call fails.
        """
        clean = {k: v for k, v in params.items() if v is not None}
        clean.setdefault("page", 1)
        clean.setdefault("limit", 100)
        encoded = {
            k: ("true" if v is True else "false" if v is False else v)
            for k, v in clean.items()
        }
        url = f"{endpoint}/search?{urlencode(encoded, doseq=True)}"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=502, detail=f"db-service search failed: {endpoint}"
            )
        return response.get("items") or []

    async def get_estate(self, estate_id: str) -> dict:
        """
        Fetch an estate by ID.

        Args:
            estate_id: Estate UUID string.

        Returns:
            Estate payload from db-service.

        Raises:
            HTTPException: 404 if the estate is missing.
        """
        url = f"{self.estates}/{estate_id}"
        response = await self.client.async_get(url)
        if not response:
            raise HTTPException(status_code=404, detail="Estate not found")
        return response

    async def get_service_catalog_map(self) -> dict[str, dict]:
        """
        Load active service catalog rows keyed by service_key.

        Returns:
            Mapping of service_key -> catalog row.
        """
        items = await self._search(
            self.service_catalog, {"is_active": True, "limit": 200}
        )
        return {i["service_key"]: i for i in items}

    async def get_ai_feature_map(self) -> dict[str, dict]:
        """
        Load active AI feature rows keyed by feature_key.

        Returns:
            Mapping of feature_key -> AI feature row.
        """
        items = await self._search(
            self.ai_feature, {"is_active": True, "limit": 200}
        )
        return {i["feature_key"]: i for i in items}

    async def get_tier_by_slug(self, slug: str) -> dict | None:
        """
        Look up a subscription tier by slug.

        Args:
            slug: Tier slug (e.g. "access", "standard").

        Returns:
            Tier row, or None if not found.
        """
        items = await self._search(
            self.subscription_tier, {"slug": slug, "limit": 1}
        )
        return items[0] if items else None

    async def get_tier_by_id(self, tier_id: str) -> dict | None:
        """
        Fetch a subscription tier by ID.

        Args:
            tier_id: Tier UUID string.

        Returns:
            Tier payload, or None if the request failed / not found.
        """
        url = f"{self.subscription_tier}/{tier_id}"
        return await self.client.async_get(url)

    async def get_active_subscription(self, estate_id: str) -> dict | None:
        """
        Return the current subscription for entitlement / billing lookups.

        Prefers healthy statuses, then cancelled/past_due (access may continue
        until period_end).

        Args:
            estate_id: Estate UUID string.

        Returns:
            Subscription row, or None if none match.
        """
        for status in ("active", "trialing", "past_due", "cancelled"):
            items = await self._search(
                self.estate_subscription,
                {"estate_id": estate_id, "status": status, "limit": 1},
            )
            if items:
                return items[0]
        return None

    async def list_estate_ai_features(self, estate_id: str) -> list[dict]:
        """
        List estate AI feature grant rows for an estate.

        Args:
            estate_id: Estate UUID string.

        Returns:
            List of estate_ai_feature rows.
        """
        return await self._search(
            self.estate_ai_feature,
            {"estate_id": estate_id, "limit": 200},
        )

    async def get_prices_for_country(self, country_code: str) -> list[dict]:
        """
        List active feature unit prices for a country.

        Args:
            country_code: ISO country code used for pricing.

        Returns:
            List of feature_unit_price rows.
        """
        return await self._search(
            self.feature_unit_price,
            {
                "country_code": country_code,
                "is_active": True,
                "limit": 500,
            },
        )

    async def create_estate_subscription(self, payload: dict) -> dict:
        """POST a new estate_subscription row."""
        response = await self.client.async_post(
            self.estate_subscription, json_data=payload
        )
        if not response:
            raise HTTPException(
                status_code=502, detail="Failed to create estate_subscription"
            )
        return response

    async def update_estate_subscription(
        self, subscription_id: str, payload: dict
    ) -> dict:
        """PATCH an estate_subscription by id."""
        url = f"{self.estate_subscription}/{subscription_id}"
        response = await self.client.async_patch(url, json_data=payload)
        if not response:
            raise HTTPException(
                status_code=502, detail="Failed to update estate_subscription"
            )
        return response

    async def create_estate_ai_feature(self, payload: dict) -> dict:
        """POST a new estate_ai_feature grant."""
        response = await self.client.async_post(
            self.estate_ai_feature, json_data=payload
        )
        if not response:
            raise HTTPException(
                status_code=502, detail="Failed to create estate_ai_feature"
            )
        return response

    async def update_estate_ai_feature(
        self, grant_id: str, payload: dict
    ) -> dict:
        """PATCH an estate_ai_feature grant by id."""
        url = f"{self.estate_ai_feature}/{grant_id}"
        response = await self.client.async_patch(url, json_data=payload)
        if not response:
            raise HTTPException(
                status_code=502, detail="Failed to update estate_ai_feature"
            )
        return response

    async def delete_estate_subscription(self, subscription_id: str) -> None:
        """Soft-delete an estate_subscription by id."""
        url = f"{self.estate_subscription}/{subscription_id}"
        await self.client.async_delete(url)

    async def delete_estate_ai_feature(self, grant_id: str) -> None:
        """Soft-delete an estate_ai_feature grant by id."""
        url = f"{self.estate_ai_feature}/{grant_id}"
        await self.client.async_delete(url)

    async def list_estate_subscriptions(self, estate_id: str) -> list[dict]:
        """List subscriptions for an estate (any status)."""
        return await self._search(
            self.estate_subscription,
            {"estate_id": estate_id, "limit": 50},
        )
