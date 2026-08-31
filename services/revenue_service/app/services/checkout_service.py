"""Checkout quote, Paystack initialization, and seat/AI quote services."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.checkout_token import (
    generate_checkout_token,
    verify_checkout_token,
)
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

logger = logging.getLogger(__name__)


class CheckoutService:
    """Builds pricing quotes from estate country, tier, and entitlements."""

    def __init__(self, repo: DbRevenueRepository):
        """
        Bind the db-service revenue repository and Paystack client.

        Args:
            repo: Repository used for estate, catalog, and price lookups.
        """
        self.repo = repo
        self._paystack = PaystackClient(
            secret_key=settings.PAYSTACK_SECRET_KEY
        )

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

    async def _get_quote_for_kind(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Compute a pricing quote for the given checkout_kind.

        Returns a dict with ``amount`` (float), ``currency_code``,
        ``country_code``, and ``snapshot`` (full quote breakdown dict).
        """
        kind = request["checkout_kind"]
        estate_id = request["estate_id"]

        if kind in ("tier", "custom"):
            result = await self.quote(
                {
                    "estate_id": estate_id,
                    "tier_slug": request.get("tier_slug"),
                    "entitlements": request.get("entitlements"),
                    "ai_feature_keys": request.get("ai_feature_keys"),
                    "covered_users": request["covered_users"],
                    "period_months": request["period_months"],
                }
            )
            return {
                "amount": result["client_total"],
                "currency_code": result["currency_code"],
                "country_code": result["country_code"],
                "snapshot": result,
            }

        if kind == "seat_add":
            result = await self.prorate_seats(
                {
                    "estate_id": estate_id,
                    "seats_added": request["seats_added"],
                }
            )
            return {
                "amount": result["prorated_charge"],
                "currency_code": result["currency_code"],
                "country_code": result["country_code"],
                "snapshot": result,
            }

        # ai_only
        result = await self.quote_ai_features(
            {
                "estate_id": estate_id,
                "ai_feature_keys": request["ai_feature_keys"],
                "period_months": request.get("period_months", 1),
            }
        )
        return {
            "amount": result["client_total"],
            "currency_code": result["currency_code"],
            "country_code": result["country_code"],
            "snapshot": result,
        }

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
        # administrative_fee is in entitlements (True/False), not tier slug.
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

    async def initialize(
        self,
        request: dict[str, Any],
        idempotency_key: str,
        current_user_id: str,
    ) -> dict[str, Any]:
        """
        Initialize a Paystack checkout transaction.

        Creates a pending checkout session, calls Paystack, and returns
        the authorization URL and a short-lived checkout token for
        status polling.

        Args:
            request: Validated CheckoutInitializeRequest dict.
            idempotency_key: Client-supplied Idempotency-Key header value.
            current_user_id: Authenticated user UUID (for audit metadata).

        Returns:
            Dict with checkout_session_id, paystack_reference,
            authorization_url, and checkout_token.

        Raises:
            HTTPException: 409 on terminal idempotency key re-use;
                502 if Paystack fails.
        """
        # 1. Idempotency check
        if len(idempotency_key) > 255:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key exceeds maximum length of 255 chars",
            )
        existing = await self.repo.get_checkout_session_by_idempotency_key(
            idempotency_key
        )
        if existing:
            if existing["status"] in ("failed", "expired"):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "A session for this idempotency key has already "
                        "failed or expired. Use a new key to retry."
                    ),
                )
            # pending or paid: return cached response (idempotent)
            meta = existing.get("session_metadata") or {}
            return {
                "checkout_session_id": str(existing["id"]),
                "paystack_reference": existing.get("paystack_reference", ""),
                "authorization_url": meta.get("authorization_url", ""),
                "checkout_token": generate_checkout_token(
                    str(existing["id"]), settings.SECRET_KEY
                ),
            }

        # 2. Guard: block new subscription checkout when one is already active.
        #    seat_add and ai_only are additive — they are always allowed.
        kind = request["checkout_kind"]
        if kind in ("tier", "custom"):
            active_sub = await self.repo.get_active_subscription(
                request["estate_id"]
            )
            if active_sub and active_sub.get("status") in (
                "active",
                "trialing",
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Estate already has an active subscription. "
                        "Wait for it to expire, or cancel it first "
                        "to subscribe to a different tier."
                    ),
                )

        # 3. Compute quote
        quote_result = await self._get_quote_for_kind(request)
        amount: float = quote_result["amount"]
        currency: str = quote_result["currency_code"]
        country: str = quote_result["country_code"]
        snapshot: dict = quote_result["snapshot"]

        # 4. Build session_metadata
        session_metadata: dict[str, Any] = {
            "checkout_kind": kind,
            "initiated_by_user_id": current_user_id,
        }
        if kind in ("tier", "custom"):
            session_metadata["tier_slug"] = (
                request.get("tier_slug") if kind == "tier" else "custom"
            )
            session_metadata["covered_users"] = request.get("covered_users")
            session_metadata["period_months"] = request.get("period_months")
            session_metadata["ai_feature_keys"] = (
                request.get("ai_feature_keys") or []
            )
            if kind == "custom":
                session_metadata["entitlements"] = request.get("entitlements")
        elif kind == "seat_add":
            session_metadata["seats_added"] = request.get("seats_added")
        elif kind == "ai_only":
            session_metadata["ai_feature_keys"] = (
                request.get("ai_feature_keys") or []
            )
            session_metadata["period_months"] = request.get("period_months")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported checkout_kind: {kind!r}",
            )

        # 5. Create pending session (no paystack_reference yet)
        session = await self.repo.create_checkout_session(
            {
                "estate_id": request["estate_id"],
                "idempotency_key": idempotency_key,
                "status": "pending",
                "pricing_snapshot": snapshot,
                "amount": str(amount),
                "currency_code": currency,
                "country_code": country,
                "checkout_kind": kind,
                "session_metadata": session_metadata,
            }
        )
        session_id = str(session["id"])

        # 6. Stamp the reference (GP-<session_id>)
        paystack_reference = f"GP-{session_id}"
        await self.repo.update_checkout_session(
            session_id, {"paystack_reference": paystack_reference}
        )

        # 7. Call Paystack
        amount_kobo = round(amount * 100)
        try:
            paystack_data = await self._paystack.initialize_transaction(
                email=request["customer_email"],
                amount_kobo=amount_kobo,
                reference=paystack_reference,
                callback_url=settings.PAYSTACK_CALLBACK_URL,
                metadata=session_metadata,
                currency=currency,
            )
        except HTTPException as exc:
            await self.repo.update_checkout_session(
                session_id,
                {
                    "status": "failed",
                    "session_metadata": {
                        **session_metadata,
                        "paystack_error": exc.detail,
                    },
                },
            )
            raise

        # 7. Persist authorization_url for idempotent replays
        authorization_url: str = paystack_data["authorization_url"]
        await self.repo.update_checkout_session(
            session_id,
            {
                "session_metadata": {
                    **session_metadata,
                    "authorization_url": authorization_url,
                    "access_code": paystack_data.get("access_code"),
                }
            },
        )

        # 8. Mint checkout token
        checkout_token = generate_checkout_token(
            session_id, settings.SECRET_KEY
        )
        return {
            "checkout_session_id": session_id,
            "paystack_reference": paystack_reference,
            "authorization_url": authorization_url,
            "checkout_token": checkout_token,
        }

    async def get_status(
        self,
        paystack_reference: str,
        checkout_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Return the current status of a checkout session.

        If a checkout_token is supplied it is verified against the session.
        If absent, the lookup proceeds by reference only (rate-limiting
        must be enforced at gateway level for this endpoint).

        Args:
            paystack_reference: Paystack transaction reference.
            checkout_token: Optional Bearer token from the initialize
                response.

        Returns:
            CheckoutStatusResponse-compatible dict.

        Raises:
            HTTPException: 404 if not found; 401/403 on token mismatch.
        """
        session = await self.repo.get_checkout_session_by_reference(
            paystack_reference
        )
        if not session:
            raise HTTPException(
                status_code=404, detail="Checkout session not found"
            )

        if checkout_token:
            session_id_from_token = verify_checkout_token(
                checkout_token, settings.SECRET_KEY
            )
            if not session_id_from_token:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired checkout_token",
                )
            if session_id_from_token != str(session["id"]):
                raise HTTPException(
                    status_code=403,
                    detail="Token does not match this session",
                )

        estate_id = str(session["estate_id"])
        paid_at = session.get("paid_at")
        return {
            "paystack_reference": paystack_reference,
            "status": session["status"],
            "checkout_kind": session["checkout_kind"],
            "paid_at": (
                paid_at.isoformat()
                if hasattr(paid_at, "isoformat")
                else paid_at
            ),
            "estate_id_masked": estate_id[:8] + "***",
        }
