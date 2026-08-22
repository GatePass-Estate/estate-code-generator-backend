"""Request/response schemas for estate subscription APIs."""

from typing import Any

from pydantic import BaseModel, Field


class EstateSubscriptionResponse(BaseModel):
    """Active subscription, tier, and effective entitlements for an estate."""

    estate_id: str
    subscription: dict[str, Any] | None = None
    tier: dict[str, Any] | None = None
    effective_entitlements: dict[str, Any] = Field(default_factory=dict)
