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


class ScheduleTierChangeRequest(BaseModel):
    """Request body for POST /estate/{id}/schedule-tier-change."""

    tier_slug: str


class ScheduleTierChangeResponse(BaseModel):
    """Response for schedule-tier-change POST and DELETE."""

    estate_id: str
    pending_tier_slug: str | None = None
    effective_from: str | None = None


class BillingCycleResponse(BaseModel):
    """Response for GET /estate/{estate_id}/billing-cycle.

    Surfaces what the *next* auto-renewal will charge and under
    which tier. The current-period summary provides just enough
    context (renewal date, seat count, auto_renew flag) without
    duplicating the full subscription + entitlements already
    returned by GET /estate/{estate_id}.
    """

    estate_id: str

    # ── Current period (billing-relevant summary only) ──────
    period_end: str | None = None
    covered_users: int | None = None
    auto_renew: bool = False
    current_tier_slug: str | None = None

    # ── Next billing projection ──────────────────────────────
    next_renewal_date: str | None = None
    tier_change_scheduled: bool = False
    next_tier_slug: str | None = None
    next_tier: dict[str, Any] | None = None
    next_billing_amount: float | None = None
    next_billing_currency: str | None = None
