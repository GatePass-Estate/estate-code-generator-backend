"""Request/response schemas for checkout quote APIs."""

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class QuoteRequest(BaseModel):
    """Body for computing a subscription or custom-entitlements quote."""

    estate_id: str
    tier_slug: str | None = None
    entitlements: dict[str, Any] | None = None
    ai_feature_keys: list[str] | None = None
    covered_users: int = Field(..., ge=1)
    period_months: Literal[1, 3, 6, 12]

    @model_validator(mode="after")
    def require_tier_or_custom(self):
        """Require either a tier_slug or entitlements map for custom quotes."""
        if not self.tier_slug and self.entitlements is None:
            raise ValueError(
                "Provide tier_slug or entitlements (custom quote)"
            )
        return self


class QuoteResponse(BaseModel):
    """Pricing breakdown returned by the checkout quote endpoint."""

    estate_id: str
    country_code: str
    currency_code: str
    price_per_seat: Any
    seats: int
    ai_price_per_month: Any
    monthly_subtotal: Any
    period_months: int
    client_total: Any
    administrative_fee: Any
    sum_of_included_features: Any
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    tier_slug: str | None = None


class SeatProrateRequest(BaseModel):
    """Body for mid-period seat-add proration quote."""

    estate_id: str
    seats_added: int = Field(..., ge=1)


class SeatProrateResponse(BaseModel):
    """Mid-period seat proration breakdown (AI excluded)."""

    estate_id: str
    subscription_id: str
    current_covered_users: int
    seats_added: int
    country_code: str
    currency_code: str
    price_per_seat: Any
    period_months: int
    period_seat_price: Any
    period_days: int
    remaining_days: int
    daily_seat_rate: Any
    prorated_charge: Any
    period_start: str
    period_end: str


class AiCheckoutRequest(BaseModel):
    """Standalone AI feature quote body."""

    estate_id: str
    ai_feature_keys: list[str] = Field(..., min_length=1)
    period_months: Literal[1, 3, 6, 12] = 1
    paid_at: str | None = None


class ActivateSubscriptionRequest(BaseModel):
    """Activate subscription after charge success (no Paystack)."""

    estate_id: str
    tier_slug: str
    covered_users: int = Field(..., ge=1)
    period_months: int = Field(..., ge=1)
    entitlements: dict[str, Any] | None = None
    ai_feature_keys: list[str] | None = None
    paid_at: str | None = None


class RenewSubscriptionRequest(BaseModel):
    """Manual renew body (dating rules applied server-side)."""

    period_months: int = Field(1, ge=1)
    paid_at: str | None = None


class CheckoutInitializeRequest(BaseModel):
    """Body for POST /checkout/initialize."""

    estate_id: str
    customer_email: EmailStr
    checkout_kind: Literal["tier", "custom", "seat_add", "ai_only"]
    tier_slug: str | None = None
    entitlements: dict[str, Any] | None = None
    ai_feature_keys: list[str] | None = None
    covered_users: int | None = Field(None, ge=1)
    seats_added: int | None = Field(None, ge=1)
    period_months: Literal[1, 3, 6, 12] = 1

    @model_validator(mode="after")
    def validate_kind_fields(self):
        """Enforce required and reject irrelevant fields per checkout_kind."""
        kind = self.checkout_kind

        # Required fields per kind
        if kind in ("tier", "custom") and self.covered_users is None:
            raise ValueError(
                f"covered_users is required for checkout_kind={kind!r}"
            )
        if kind == "tier" and not self.tier_slug:
            raise ValueError("tier_slug is required for checkout_kind='tier'")
        if kind == "custom" and self.entitlements is None:
            raise ValueError(
                "entitlements is required for checkout_kind='custom'"
            )
        if kind == "seat_add" and self.seats_added is None:
            raise ValueError(
                "seats_added is required for checkout_kind='seat_add'"
            )
        if kind == "ai_only" and not self.ai_feature_keys:
            raise ValueError(
                "ai_feature_keys is required for checkout_kind='ai_only'"
            )

        # seat_add has no billing period — reject if explicitly provided.
        # period_months has a default (1) so we use model_fields_set to
        # distinguish an explicit value from the default.
        if kind == "seat_add" and "period_months" in self.model_fields_set:
            raise ValueError(
                "period_months is not allowed for checkout_kind='seat_add'"
            )

        # Reject fields that don't belong to this kind.
        # ai_feature_keys is allowed on tier/custom (bundles AI with sub).
        forbidden_map: dict[str, set[str]] = {
            "tier": {"seats_added", "entitlements"},
            "custom": {"seats_added", "tier_slug"},
            "seat_add": {
                "tier_slug",
                "entitlements",
                "covered_users",
                "ai_feature_keys",
            },
            "ai_only": {
                "tier_slug",
                "entitlements",
                "covered_users",
                "seats_added",
            },
        }
        forbidden = [
            f
            for f in forbidden_map.get(kind, set())
            if getattr(self, f) is not None
        ]
        if forbidden:
            fields = ", ".join(sorted(forbidden))
            verb = "is" if len(forbidden) == 1 else "are"
            raise ValueError(
                f"{fields} {verb} not allowed for" f" checkout_kind={kind!r}"
            )

        return self


class CheckoutInitializeResponse(BaseModel):
    """Response for POST /checkout/initialize."""

    checkout_session_id: str
    paystack_reference: str
    authorization_url: str
    checkout_token: str


class CheckoutStatusResponse(BaseModel):
    """Response for GET /checkout/status/{reference}."""

    paystack_reference: str
    status: str
    checkout_kind: str
    paid_at: str | None = None
    estate_id_masked: str
