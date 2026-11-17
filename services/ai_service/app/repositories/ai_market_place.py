"""HTTP access to db-service catalog/ratings and revenue-service billing."""

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class AiMarketPlaceRepository:
    """Outbound calls used by the AI marketplace service."""

    def __init__(self, http_client: AsyncHttpHandler) -> None:
        """Bind the HTTP client and compose db-service and revenue-service URLs."""
        self.client = http_client
        base = settings.DB_SERVICE_URL.rstrip("/") + "/"
        revenue = settings.REVENUE_SERVICE_URL.rstrip("/") + "/"
        self.marketplace = f"{base}api/v1/revenue/aimarketplacefeature"
        self.ratings = f"{base}api/v1/revenue/aimarketplacefeaturerating"
        self.ai_feature = f"{base}api/v1/revenue/aifeature"
        self.estate_ai_feature = f"{base}api/v1/revenue/estateaifeature"
        self.feature_unit_price = f"{base}api/v1/revenue/featureunitprice"
        self.estates = f"{base}api/v1/userprofile/estates"
        self.revenue_checkout = f"{revenue}api/v1/checkout"
        self.revenue_ai = f"{revenue}api/v1/ai-features"

    async def _search(self, endpoint: str, params: dict[str, Any]) -> dict:
        """GET ``endpoint/search`` with query params; raise 502 if missing."""
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
        return response

    async def list_products(
        self, *, category: list[str] | None, page: int, limit: int
    ) -> dict:
        """Search active marketplace products, optionally by category."""
        return await self._search(
            self.marketplace,
            {
                "category": category or None,
                "is_active": True,
                "page": page,
                "limit": limit,
            },
        )

    async def get_product(self, product_id: str) -> dict:
        """Fetch one marketplace product, or raise 404."""
        response = await self.client.async_get(
            f"{self.marketplace}/{product_id}"
        )
        if not response:
            raise HTTPException(status_code=404, detail="Feature not found")
        return response

    async def rating_summaries(self, feature_ids: list[str]) -> list[dict]:
        """Fetch bounded rating summaries for the given parent ids."""
        if not feature_ids:
            return []
        params = {"ai_marketplace_feature_id": feature_ids}
        url = f"{self.ratings}/summary?{urlencode(params, doseq=True)}"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=502, detail="Rating summary failed"
            )
        return response.get("items") or []

    async def search_rating(
        self, *, feature_id: str, user_id: str
    ) -> dict | None:
        """Return this user's rating for a product, if one exists."""
        response = await self._search(
            self.ratings,
            {
                "ai_marketplace_feature_id": feature_id,
                "user_id": user_id,
                "limit": 1,
            },
        )
        items = response.get("items") or []
        return items[0] if items else None

    async def create_rating(
        self,
        *,
        feature_id: str,
        user_id: str,
        score: int,
        comment: str | None = None,
    ) -> dict:
        """Create a rating row; raise 502 if db-service does not persist it."""
        response = await self.client.async_post(
            self.ratings,
            json_data={
                "ai_marketplace_feature_id": feature_id,
                "user_id": user_id,
                "score": score,
                "comment": comment,
            },
        )
        if not response:
            raise HTTPException(
                status_code=502, detail="Failed to save rating"
            )
        return response

    async def update_rating(
        self,
        rating_id: str,
        score: int,
        comment: str | None = None,
    ) -> dict:
        """Patch score and optional comment on an existing rating."""
        payload: dict[str, Any] = {"score": score}
        if comment is not None:
            payload["comment"] = comment
        response = await self.client.async_patch(
            f"{self.ratings}/{rating_id}", json_data=payload
        )
        if not response:
            raise HTTPException(
                status_code=502, detail="Failed to update rating"
            )
        return response

    async def get_ai_feature(self, feature_id: str) -> dict | None:
        """Fetch one ``ai_feature`` catalog row, or None if missing."""
        return await self.client.async_get(f"{self.ai_feature}/{feature_id}")

    async def list_ai_features(self) -> list[dict]:
        """List active ``ai_feature`` catalog rows."""
        response = await self._search(
            self.ai_feature, {"is_active": True, "limit": 200}
        )
        return response.get("items") or []

    async def list_estate_ai_features(self, estate_id: str) -> list[dict]:
        """List AI feature grants for an estate."""
        response = await self._search(
            self.estate_ai_feature, {"estate_id": estate_id, "limit": 200}
        )
        return response.get("items") or []

    async def get_estate(self, estate_id: str) -> dict:
        """Fetch an estate row, or raise 404."""
        response = await self.client.async_get(f"{self.estates}/{estate_id}")
        if not response:
            raise HTTPException(status_code=404, detail="Estate not found")
        return response

    async def list_prices(self, country_code: str) -> list[dict]:
        """List active AI unit prices for a country."""
        response = await self._search(
            self.feature_unit_price,
            {
                "country_code": country_code,
                "feature_kind": "ai",
                "is_active": True,
                "limit": 500,
            },
        )
        return response.get("items") or []

    async def quote_ai(
        self, estate_id: str, feature_keys: list[str], period_months: int
    ) -> dict:
        """Quote standalone AI purchase totals from revenue-service."""
        response = await self.client.async_post(
            f"{self.revenue_checkout}/ai/quote",
            json_data={
                "estate_id": estate_id,
                "ai_feature_keys": feature_keys,
                "period_months": period_months,
            },
        )
        if not response:
            raise HTTPException(status_code=502, detail="AI quote failed")
        return response

    async def activate_ai(
        self, estate_id: str, feature_keys: list[str], period_months: int
    ) -> dict:
        """Provision paid AI grants via revenue-service (Paystack still stubbed)."""
        response = await self.client.async_post(
            f"{self.revenue_ai}/estate/{estate_id}/activate",
            json_data={
                "ai_feature_keys": feature_keys,
                "period_months": period_months,
            },
        )
        if not response:
            raise HTTPException(status_code=502, detail="AI activate failed")
        return response

    async def install_ai(self, estate_id: str, feature_key: str) -> dict:
        """Install a free AI feature grant via revenue-service."""
        response = await self.client.async_post(
            f"{self.revenue_ai}/estate/{estate_id}/install",
            json_data={"feature_key": feature_key},
        )
        if not response:
            raise HTTPException(status_code=502, detail="AI install failed")
        return response

    async def get_picture_bytes(self, gcs_path: str) -> tuple[bytes, str]:
        """GET picture bytes from db-service for a catalog GCS path."""
        url = (
            f"{self.marketplace}/picture/stream"
            f"?{urlencode({'path': gcs_path})}"
        )
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as http_client:
            try:
                response = await http_client.get(url)
                response.raise_for_status()
                media_type = response.headers.get("content-type", "image/jpeg")
                return response.content, media_type
            except httpx.HTTPStatusError as e:
                detail = e.response.text
                try:
                    detail = e.response.json().get("detail", detail)
                except ValueError:
                    pass
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=detail,
                ) from e
            except httpx.RequestError as e:
                logger.exception("Marketplace picture fetch failed")
                raise HTTPException(
                    status_code=503,
                    detail="Picture stream unavailable",
                ) from e
