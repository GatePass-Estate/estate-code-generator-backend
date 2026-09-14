"""Checkout quote, Paystack initialization, and seat/AI quote services."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
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
from app.schemas.estate import EstateTypeMultiplier
from app.services.pricing_service import (
    VAT_KEY,
    apply_vat,
    compute_ai_monthly,
    compute_seat_proration,
    quote_pricing,
    round_charge,
)

logger = logging.getLogger(__name__)


# ── Per-kind checkout handlers ─────────────────────────────────────────────


class CheckoutHandler(ABC):
    """Abstract base for checkout-kind-specific logic.

    Each concrete handler encapsulates the guard, quote, and metadata
    logic for one checkout kind so that adding a new kind is a new class
    rather than a new if/else branch in CheckoutService.initialize().
    """

    def __init__(
        self, repo: DbRevenueRepository, svc: CheckoutService
    ) -> None:
        self._repo = repo
        self._svc = svc

    @abstractmethod
    async def guard(self, request: dict[str, Any]) -> None:
        """Raise HTTPException if this checkout cannot proceed."""
        ...

    @abstractmethod
    async def get_quote(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return {amount, currency_code, country_code, snapshot}."""
        ...

    @abstractmethod
    def build_metadata(
        self, request: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """Build the session_metadata dict for this checkout kind."""
        ...


class SubscriptionCheckoutHandler(CheckoutHandler):
    """Handles 'tier' and 'custom' subscription checkout kinds."""

    async def guard(self, request: dict[str, Any]) -> None:
        active_sub = await self._repo.get_active_subscription(
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

    async def get_quote(self, request: dict[str, Any]) -> dict[str, Any]:
        result = await self._svc.quote(
            {
                "estate_id": request["estate_id"],
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

    def build_metadata(
        self, request: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        kind = request["checkout_kind"]
        meta: dict[str, Any] = {
            "checkout_kind": kind,
            "initiated_by_user_id": user_id,
            "tier_slug": (
                request.get("tier_slug") if kind == "tier" else "custom"
            ),
            "covered_users": request.get("covered_users"),
            "period_months": request.get("period_months"),
            "ai_feature_keys": request.get("ai_feature_keys") or [],
        }
        if kind == "custom":
            meta["entitlements"] = request.get("entitlements")
        return meta


class SeatAddCheckoutHandler(CheckoutHandler):
    """Handles 'seat_add' checkout kind."""

    async def guard(self, request: dict[str, Any]) -> None:
        pass  # seat additions are always allowed for active subscriptions

    async def get_quote(self, request: dict[str, Any]) -> dict[str, Any]:
        result = await self._svc.prorate_seats(
            {
                "estate_id": request["estate_id"],
                "seats_added": request["seats_added"],
            }
        )
        return {
            "amount": result["prorated_charge"],
            "currency_code": result["currency_code"],
            "country_code": result["country_code"],
            "snapshot": result,
        }

    def build_metadata(
        self, request: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        return {
            "checkout_kind": "seat_add",
            "initiated_by_user_id": user_id,
            "seats_added": request.get("seats_added"),
        }


class AiOnlyCheckoutHandler(CheckoutHandler):
    """Handles 'ai_only' standalone AI feature checkout kind."""

    async def guard(self, request: dict[str, Any]) -> None:
        await self._svc.guard_no_active_ai_grants(
            estate_id=str(request["estate_id"]),
            ai_feature_keys=list(request.get("ai_feature_keys") or []),
        )

    async def get_quote(self, request: dict[str, Any]) -> dict[str, Any]:
        result = await self._svc.quote_ai_features(
            {
                "estate_id": request["estate_id"],
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

    def build_metadata(
        self, request: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        return {
            "checkout_kind": "ai_only",
            "initiated_by_user_id": user_id,
            "ai_feature_keys": request.get("ai_feature_keys") or [],
            "period_months": request.get("period_months"),
        }


_HANDLERS: dict[str, type[CheckoutHandler]] = {
    "tier": SubscriptionCheckoutHandler,
    "custom": SubscriptionCheckoutHandler,
    "seat_add": SeatAddCheckoutHandler,
    "ai_only": AiOnlyCheckoutHandler,
}


# ── Service ────────────────────────────────────────────────────────────────


class CheckoutService:
    """Builds quotes from estate type, country prices, and VAT."""

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

    @staticmethod
    def _estate_multiplier(estate_type: str | None) -> float:
        """Resolve the env-backed multiplier for the estate's type."""
        if not estate_type:
            raise HTTPException(
                status_code=400,
                detail="Estate has no estate_type set; cannot price",
            )
        factors = EstateTypeMultiplier(
            housing=settings.ESTATE_TYPE_HOUSING_MULTIPLIER,
            corporate=settings.ESTATE_TYPE_CORPORATE_MULTIPLIER,
        )
        key = str(estate_type).lower()
        if key not in factors.model_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown estate_type '{estate_type}'",
            )
        return getattr(factors, key)

    async def _pricing_context(
        self, estate_id: str
    ) -> tuple[str, dict[str, Any], dict[str, Any], str, Any]:
        """Country, scaled prices, currency, and VAT rate for an estate."""
        estate = await self.repo.get_estate(estate_id)
        country = (estate.get("country") or "").upper()
        if not country:
            raise HTTPException(
                status_code=400,
                detail="Estate has no country set; cannot price",
            )
        multiplier = self._estate_multiplier(estate.get("estate_type"))
        service_prices, ai_prices, currency, vat_rate = await self._price_maps(
            country, multiplier
        )
        return country, service_prices, ai_prices, currency, vat_rate

    async def _price_maps(
        self, country: str, multiplier: float
    ) -> tuple[dict[str, Any], dict[str, Any], str, Any]:
        """
        Return service_prices, ai_prices, currency, and VAT rate.

        Unit prices (except VAT) are multiplied by ``multiplier`` before
        any quote math. VAT is the catalog percent, unscaled.
        """
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
        vat_rate: Any = None
        factor = Decimal(str(multiplier))
        for row in prices:
            amount = row["feature_unit_price"]
            if row.get("service_catalog_id"):
                key = service_id_to_key.get(str(row["service_catalog_id"]))
                if not key:
                    continue
                if key == VAT_KEY:
                    vat_rate = amount  # percent; do not scale
                    continue
                service_prices[key] = round_charge(
                    Decimal(str(amount)) * factor
                )
            if row.get("ai_feature_id"):
                key = ai_id_to_key.get(str(row["ai_feature_id"]))
                if key:
                    ai_prices[key] = round_charge(
                        Decimal(str(amount)) * factor
                    )
        if vat_rate is None:
            raise HTTPException(
                status_code=400,
                detail=f"No VAT rate for country {country}",
            )
        return service_prices, ai_prices, currency, vat_rate

    async def quote(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Produce a checkout quote for an estate subscription purchase.

        Resolves country pricing, scales unit prices by estate type (VAT
        excluded), validates entitlements against the catalog, includes
        administrative_fee when the entitlements map sets it True, then
        applies country VAT to the finished total.

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
        (
            country,
            service_prices,
            ai_prices,
            currency,
            vat_rate,
        ) = await self._pricing_context(estate_id)

        catalog = await self.repo.get_service_catalog_map()

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

        # VAT is a rate, not a purchasable entitlement.
        limit_map = {
            k: v["limit_type"] for k, v in catalog.items() if k != VAT_KEY
        }
        validate_entitlements(entitlements, limit_map)

        # Included product keys: enabled booleans / positive limits.
        # administrative_fee is in entitlements (True/False), not tier slug.
        included_keys: list[str] = []
        for key, value in entitlements.items():
            if key == VAT_KEY:
                continue
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

        vat = apply_vat(breakdown["client_total"], vat_rate)
        return {
            "estate_id": estate_id,
            "tier_slug": tier_slug,
            **breakdown,
            # serialize Decimals as str/float-friendly
            "price_per_seat": float(breakdown["price_per_seat"]),
            "ai_price_per_month": float(breakdown["ai_price_per_month"]),
            "monthly_subtotal": float(breakdown["monthly_subtotal"]),
            "subtotal": float(vat["subtotal"]),
            "vat_rate": float(vat["vat_rate"]),
            "vat_amount": float(vat["vat_amount"]),
            "client_total": float(vat["client_total"]),
            "administrative_fee": float(breakdown["administrative_fee"]),
            "sum_of_included_features": float(
                breakdown["sum_of_included_features"]
            ),
            "line_items": [
                {**li, "unit_price": float(li["unit_price"])}
                for li in breakdown["line_items"]
            ]
            + [
                {
                    "key": VAT_KEY,
                    "kind": "vat",
                    "unit_price": float(vat["vat_amount"]),
                }
            ],
        }

    async def prorate_seats(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Quote a mid-period seat add (AI excluded from proration).

        Uses the active subscription period and current tier seat price.
        Estate-type multiplier applies to unit prices; VAT is added last.
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

        (
            country,
            service_prices,
            _ai_prices,
            currency,
            vat_rate,
        ) = await self._pricing_context(estate_id)

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

        included_keys: list[str] = []
        for key, value in entitlements.items():
            if key == VAT_KEY:
                continue
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

        vat = apply_vat(prorated["prorated_charge"], vat_rate)
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
            "subtotal": float(vat["subtotal"]),
            "vat_rate": float(vat["vat_rate"]),
            "vat_amount": float(vat["vat_amount"]),
            "prorated_charge": float(vat["client_total"]),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

    async def quote_ai_features(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Quote standalone AI feature flats (not × seats).

        Estate-type multiplier applies to unit prices; VAT is added last.
        """
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

        (
            country,
            _service_prices,
            ai_prices,
            currency,
            vat_rate,
        ) = await self._pricing_context(estate_id)
        try:
            ai = compute_ai_monthly(ai_prices, feature_keys)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        monthly = float(round_charge(ai["ai_price_per_month"]))
        total = round_charge(ai["ai_price_per_month"] * period_months)
        vat = apply_vat(total, vat_rate)
        return {
            "estate_id": estate_id,
            "country_code": country,
            "currency_code": currency,
            "ai_feature_keys": feature_keys,
            "period_months": period_months,
            "ai_price_per_month": monthly,
            "subtotal": float(vat["subtotal"]),
            "vat_rate": float(vat["vat_rate"]),
            "vat_amount": float(vat["vat_amount"]),
            "client_total": float(vat["client_total"]),
            "line_items": [
                {**li, "unit_price": float(li["unit_price"])}
                for li in ai["line_items"]
            ]
            + [
                {
                    "key": VAT_KEY,
                    "kind": "vat",
                    "unit_price": float(vat["vat_amount"]),
                }
            ],
        }

    async def guard_no_active_ai_grants(
        self,
        estate_id: str,
        ai_feature_keys: list[str],
    ) -> None:
        """Raise 409 if any requested feature key already has a live grant.

        A grant is considered live when its status is 'active' and either
        expires_at is absent or still in the future.
        """
        if not ai_feature_keys:
            return
        catalog = await self.repo.get_ai_feature_map()
        key_to_feature_id = {k: str(v["id"]) for k, v in catalog.items()}
        grants = await self.repo.list_estate_ai_features(estate_id)
        grant_by_feature_id = {str(g.get("ai_feature_id")): g for g in grants}
        now = datetime.now(tz=timezone.utc)
        conflicting: list[str] = []
        for key in ai_feature_keys:
            feature_id = key_to_feature_id.get(key)
            if not feature_id:
                continue
            grant = grant_by_feature_id.get(feature_id)
            if not grant:
                continue
            status = (grant.get("status") or "").lower()
            if status != "active":
                continue
            expires_raw = grant.get("expires_at")
            if expires_raw:
                expires_at = datetime.fromisoformat(
                    str(expires_raw).replace("Z", "+00:00")
                )
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= now:
                    continue
            conflicting.append(key)
        if conflicting:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Estate already has an active grant for: "
                    f"{', '.join(conflicting)}. "
                    "Wait for expiry, cancel the existing grant, or "
                    "upgrade to a higher tier."
                ),
            )

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

        # 2. Resolve handler for this checkout kind
        kind = request["checkout_kind"]
        handler_cls = _HANDLERS.get(kind)
        if not handler_cls:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported checkout_kind: {kind!r}",
            )
        handler = handler_cls(self.repo, self)

        # 3. Kind-specific guard (raises 409 on conflict)
        await handler.guard(request)

        # 4. Compute quote
        quote_result = await handler.get_quote(request)
        amount: float = quote_result["amount"]
        currency: str = quote_result["currency_code"]
        country: str = quote_result["country_code"]
        snapshot: dict = quote_result["snapshot"]

        # 5. Build session_metadata
        session_metadata = handler.build_metadata(request, current_user_id)

        # 6. Create pending session (no paystack_reference yet)
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

        # 7. Stamp the reference (GP-<session_id>)
        paystack_reference = f"GP-{session_id}"
        await self.repo.update_checkout_session(
            session_id, {"paystack_reference": paystack_reference}
        )

        # 8. Call Paystack
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

        # 9. Persist authorization_url for idempotent replays
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

        # 10. Mint checkout token
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
            CheckoutStatusResponse-compatible dict plus ``estate_id``
            for the caller to enforce membership before responding.

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
            "estate_id": estate_id,
            "estate_id_masked": estate_id[:8] + "***",
        }
