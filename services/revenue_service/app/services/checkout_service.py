"""Checkout quote + Paystack stubs."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.libs.entitlement_validation import validate_entitlements
from app.repositories.db_revenue import DbRevenueRepository
from app.services.pricing_service import ADMIN_FEE_KEY, quote_pricing

logger = logging.getLogger(__name__)


class CheckoutService:
    """Builds pricing quotes from estate country, tier, and entitlements."""

    def __init__(self, repo: DbRevenueRepository):
        """
        Bind the db-service revenue repository.

        Args:
            repo: Repository used for estate, catalog, and price lookups.
        """
        self.repo = repo

    async def quote(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Produce a checkout quote for an estate subscription purchase.

        Resolves country pricing, validates entitlements against the catalog,
        applies administrative-fee rules for paid tiers, and returns a
        float-serialized breakdown.

        Args:
            request: Quote request dict (estate_id, covered_users,
                period_months, optional tier_slug / entitlements /
                ai_feature_keys).

        Returns:
            Quote response with totals and line_items (floats).

        Raises:
            HTTPException: 400/404 on validation or missing pricing data.
        """
        estate_id = request["estate_id"]
        estate = await self.repo.get_estate(estate_id)
        country = (estate.get("country") or "").upper()
        if not country:
            raise HTTPException(
                status_code=400,
                detail="Estate has no country set; cannot price",
            )

        catalog = await self.repo.get_service_catalog_map()
        ai_catalog = await self.repo.get_ai_feature_map()
        prices = await self.repo.get_prices_for_country(country)
        if not prices:
            raise HTTPException(
                status_code=400,
                detail=f"No feature_unit_price rows for country {country}",
            )
        currency = prices[0].get("currency_code", "NGN")

        # Build price maps keyed by catalog keys
        service_id_to_key = {str(v["id"]): k for k, v in catalog.items()}
        ai_id_to_key = {str(v["id"]): k for k, v in ai_catalog.items()}
        service_prices: dict[str, Any] = {}
        ai_prices: dict[str, Any] = {}
        for row in prices:
            amount = row["feature_unit_price"]
            if row.get("service_catalog_id"):
                key = service_id_to_key.get(str(row["service_catalog_id"]))
                if key:
                    service_prices[key] = amount
            if row.get("ai_feature_id"):
                key = ai_id_to_key.get(str(row["ai_feature_id"]))
                if key:
                    ai_prices[key] = amount

        tier_slug = request.get("tier_slug")
        entitlements = request.get("entitlements")
        ai_keys = list(request.get("ai_feature_keys") or [])

        if tier_slug:
            tier = await self.repo.get_tier_by_slug(tier_slug)
            if not tier:
                raise HTTPException(
                    status_code=404, detail=f"Unknown tier '{tier_slug}'"
                )
            if tier.get("is_custom") and entitlements is None:
                raise HTTPException(
                    status_code=400,
                    detail="Custom tier requires entitlements in quote body",
                )
            if not tier.get("is_custom"):
                entitlements = tier.get("entitlements") or {}
                if not ai_keys:
                    ai_keys = list(tier.get("included_ai_features") or [])
            else:
                entitlements = entitlements or {}
        else:
            entitlements = entitlements or {}

        # Validate custom/tier entitlements against catalog
        limit_map = {k: v["limit_type"] for k, v in catalog.items()}
        validate_entitlements(entitlements, limit_map)

        # Included product keys: enabled booleans / positive limits
        included_keys: list[str] = []
        for key, value in entitlements.items():
            if key == ADMIN_FEE_KEY:
                continue
            if isinstance(value, bool) and value:
                included_keys.append(key)
            elif isinstance(value, int) and value > 0:
                included_keys.append(key)

        # Paid tiers include administrative_fee when true or when not Access
        if entitlements.get(ADMIN_FEE_KEY) is True or (
            tier_slug and tier_slug != "access"
        ):
            if ADMIN_FEE_KEY not in included_keys:
                included_keys.append(ADMIN_FEE_KEY)

        # Access: no admin fee / zero prices expected
        if tier_slug == "access":
            included_keys = [k for k in included_keys if k != ADMIN_FEE_KEY]

        try:
            breakdown = quote_pricing(
                service_prices=service_prices,
                ai_prices=ai_prices,
                included_service_keys=included_keys,
                ai_feature_keys=ai_keys,
                seats=int(request["covered_users"]),
                period_months=int(request["period_months"]),
                currency_code=currency,
                country_code=country,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        return {
            "estate_id": estate_id,
            "tier_slug": tier_slug,
            **breakdown,
            # serialize Decimals as str/float-friendly
            "price_per_seat": float(breakdown["price_per_seat"]),
            "ai_price_per_month": float(breakdown["ai_price_per_month"]),
            "monthly_subtotal": float(breakdown["monthly_subtotal"]),
            "client_total": float(breakdown["client_total"]),
            "administrative_fee": float(breakdown["administrative_fee"]),
            "sum_of_included_features": float(
                breakdown["sum_of_included_features"]
            ),
            "line_items": [
                {**li, "unit_price": float(li["unit_price"])}
                for li in breakdown["line_items"]
            ],
        }
