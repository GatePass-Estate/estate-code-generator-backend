"""Request/response schemas for estate subscription APIs."""

from typing import Any

from pydantic import BaseModel, Field


class EstateSubscriptionResponse(BaseModel):
    """Active subscription, tier, and effective entitlements for an estate."""

    estate_id: str
    subscription: dict[str, Any] | None = None
    tier: dict[str, Any] | None = None
    effective_entitlements: dict[str, Any] = Field(default_factory=dict)


class ActivateSubscriptionResponse(BaseModel):
    """Result of subscription activation (charge-success companion)."""

    estate_id: str
    subscription_id: str
    subscription: dict[str, Any] | None = None
    tier_slug: str
    entitlements_snapshot: dict[str, Any] | None = None
    effective_entitlements: dict[str, Any] = Field(default_factory=dict)
    period_end: str


class MutationSubscriptionResponse(BaseModel):
    """Generic subscription mutation response (renew / cancel / seats)."""

    estate_id: str
    subscription: dict[str, Any] | None = None
    period_end: str | None = None
    covered_users: int | None = None
