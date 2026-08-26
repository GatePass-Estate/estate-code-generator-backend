"""Request/response schemas for entitlement and AI feature APIs."""

from typing import Any

from pydantic import BaseModel, Field


class EntitlementCheckResponse(BaseModel):
    """Result of checking a single service_key entitlement for an estate."""

    estate_id: str
    service_key: str
    allowed: bool
    limit: Any = None
    limit_type: str | None = None
    locked: bool = False
    reason: str | None = None
    covered_users: int | None = None
    subscription_status: str | None = None
    tier_slug: str | None = None


class EstateEntitlementsResponse(BaseModel):
    """Full effective entitlements map for an estate."""

    estate_id: str
    entitlements: dict[str, Any] = Field(default_factory=dict)
    locked: bool = False
    reason: str | None = None
    covered_users: int | None = None
    subscription_status: str | None = None
    tier_slug: str | None = None


class AiFeatureCheckResponse(BaseModel):
    """Result of checking whether an estate may use an AI feature."""

    estate_id: str
    feature_key: str
    allowed: bool
    is_free: bool = False
    status: str | None = None
    expires_at: str | None = None
    is_installed: bool | None = None


class EstateAiFeaturesResponse(BaseModel):
    """List of AI feature grants for an estate."""

    estate_id: str
    features: list[dict[str, Any]] = Field(default_factory=list)


class AiActivateRequest(BaseModel):
    """Body for standalone AI grant activation after charge success."""

    ai_feature_keys: list[str] = Field(..., min_length=1)
    period_months: int = Field(1, ge=1)
    paid_at: str | None = None
