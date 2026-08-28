"""Checkout quote, seat proration, and AI quote stubs (no Paystack)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from app.libs.entitlement_validation import (
    ensure_admin_fee_entitlement,
    validate_entitlements,
)
from app.repositories.db_revenue import DbRevenueRepository
from app.services.pricing_service import (
    compute_ai_monthly,
    compute_seat_proration,
    quote_pricing,
    round_charge,
)
from app.services.subscription_service import SubscriptionService

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

    async def _price_maps(
        self, country: str
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        """Return service_prices, ai_prices, currency for a country."""
        catalog = await self.repo.get_service_catalog_map()
        ai_catalog = await self.repo.get_ai_feature_map()
        prices = await self.repo.get_prices_for_country(country)
        if not prices:
            raise HTTPException(
                status_code=400,
                detail=f"No feature_unit_price rows for country {country}",
            )
        currency = prices[0].get("currency_code", "NGN")
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
        return service_prices, ai_prices, currency

    async def quote(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Produce a checkout quote for an estate subscription purchase.

        Resolves country pricing, validates entitlements against the catalog,
        includes administrative_fee when the entitlements map sets it True,
        and returns a float-serialized breakdown.

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
        service_prices, ai_prices, currency = await self._price_maps(country)

        tier_slug = request.get("tier_slug")
        entitlements = request.get("entitlements")
        ai_keys = list(request.get("ai_feature_keys") or [])
        tier = None

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
                entitlements = ensure_admin_fee_entitlement(entitlements or {})
        else:
            entitlements = entitlements or {}

        # Validate custom/tier entitlements against catalog
        limit_map = {k: v["limit_type"] for k, v in catalog.items()}
        validate_entitlements(entitlements, limit_map)

        # Included product keys: enabled booleans / positive limits.
        # administrative_fee is keyed in entitlements (True/False), not tier slug.
        included_keys: list[str] = []
        for key, value in entitlements.items():
            if isinstance(value, bool) and value:
                included_keys.append(key)
            elif isinstance(value, int) and value > 0:
                included_keys.append(key)

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

    async def prorate_seats(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Quote a mid-period seat add (AI excluded from proration).

        Uses the active subscription period and current tier seat price.
        """
        estate_id = request["estate_id"]
        seats_added = int(request["seats_added"])
        if seats_added < 1:
            raise HTTPException(
                status_code=400, detail="seats_added must be >= 1"
            )

        subscription = await self.repo.get_active_subscription(estate_id)
        if not subscription:
            raise HTTPException(
                status_code=404, detail="No active subscription for estate"
            )

        period_start_raw = subscription.get("period_start")
        period_end_raw = subscription.get("period_end")
        if not period_start_raw or not period_end_raw:
            raise HTTPException(
                status_code=400,
                detail="Subscription missing period_start/period_end",
            )
        period_start = datetime.fromisoformat(
            str(period_start_raw).replace("Z", "+00:00")
        )
        period_end = datetime.fromisoformat(
            str(period_end_raw).replace("Z", "+00:00")
        )

        estate = await self.repo.get_estate(estate_id)
        country = (estate.get("country") or "").upper()
        if not country:
            raise HTTPException(
                status_code=400,
                detail="Estate has no country set; cannot price",
            )

        tier = await self.repo.get_tier_by_id(str(subscription["tier_id"]))
        if not tier:
            raise HTTPException(
                status_code=404, detail="Subscription tier missing"
            )

        if tier.get("is_custom"):
            entitlements = ensure_admin_fee_entitlement(
                dict(subscription.get("entitlements") or {})
            )
        else:
            entitlements = dict(tier.get("entitlements") or {})

        service_prices, _ai_prices, currency = await self._price_maps(country)
        included_keys: list[str] = []
        for key, value in entitlements.items():
            if isinstance(value, bool) and value:
                included_keys.append(key)
            elif isinstance(value, int) and value > 0:
                included_keys.append(key)

        # Infer period_months from the subscription window (~30-day months).
        period_days = (period_end.date() - period_start.date()).days + 1
        period_months = max(1, round(period_days / 30))

        try:
            full_quote = quote_pricing(
                service_prices=service_prices,
                ai_prices={},
                included_service_keys=included_keys,
                ai_feature_keys=[],
                seats=1,
                period_months=period_months,
                currency_code=currency,
                country_code=country,
            )
            period_seat_price = round_charge(
                full_quote["price_per_seat"] * period_months
            )
            prorated = compute_seat_proration(
                period_seat_price=period_seat_price,
                seats_added=seats_added,
                period_start=period_start,
                period_end=period_end,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        return {
            "estate_id": estate_id,
            "subscription_id": str(subscription["id"]),
            "current_covered_users": int(
                subscription.get("covered_users") or 0
            ),
            "seats_added": seats_added,
            "country_code": country,
            "currency_code": currency,
            "price_per_seat": float(full_quote["price_per_seat"]),
            "period_months": period_months,
            "period_seat_price": float(prorated["period_seat_price"]),
            "period_days": prorated["period_days"],
            "remaining_days": prorated["remaining_days"],
            "daily_seat_rate": float(prorated["daily_seat_rate"]),
            "prorated_charge": float(prorated["prorated_charge"]),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

    async def apply_seat_add(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Apply a mid-period seat purchase after charge success (no Paystack).

        Bumps ``covered_users`` only; does not touch AI grants.
        """
        return await SubscriptionService(self.repo).apply_seat_add(
            request["estate_id"], int(request["seats_added"])
        )

    async def quote_ai_features(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Quote standalone AI feature flats (not × seats)."""
        estate_id = request["estate_id"]
        feature_keys = list(request.get("ai_feature_keys") or [])
        if not feature_keys:
            raise HTTPException(
                status_code=400, detail="ai_feature_keys required"
            )
        period_months = int(request.get("period_months") or 1)
        if period_months < 1:
            raise HTTPException(
                status_code=400, detail="period_months must be >= 1"
            )

        estate = await self.repo.get_estate(estate_id)
        country = (estate.get("country") or "").upper()
        if not country:
            raise HTTPException(
                status_code=400,
                detail="Estate has no country set; cannot price",
            )
        _service_prices, ai_prices, currency = await self._price_maps(country)
        try:
            ai = compute_ai_monthly(ai_prices, feature_keys)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        monthly = float(round_charge(ai["ai_price_per_month"]))
        total = round_charge(ai["ai_price_per_month"] * period_months)
        return {
            "estate_id": estate_id,
            "country_code": country,
            "currency_code": currency,
            "ai_feature_keys": feature_keys,
            "period_months": period_months,
            "ai_price_per_month": monthly,
            "client_total": float(total),
            "line_items": [
                {**li, "unit_price": float(li["unit_price"])}
                for li in ai["line_items"]
            ],
        }
