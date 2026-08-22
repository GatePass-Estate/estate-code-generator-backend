"""Request/response schemas for checkout quote APIs."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class QuoteRequest(BaseModel):
    """Body for computing a subscription or custom-entitlements quote."""

    estate_id: str
    tier_slug: str | None = None
    entitlements: dict[str, Any] | None = None
    ai_feature_keys: list[str] | None = None
    covered_users: int = Field(..., ge=1)
    period_months: int = Field(..., ge=1)

    @model_validator(mode="after")
    def require_tier_or_custom(self):
        """Require either a tier_slug or an entitlements map for custom quotes."""
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
