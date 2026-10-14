"""Subscription tier catalog (proxied from db-service)."""

from typing import Any

from pydantic import BaseModel, Field


class ServiceFeatureLabel(BaseModel):
    service_key: str
    label: str


class AiFeatureLabel(BaseModel):
    feature_key: str
    label: str


class ServiceFeatureAvailabilityGroup(BaseModel):
    available: list[ServiceFeatureLabel] = Field(default_factory=list)
    unavailable: list[ServiceFeatureLabel] = Field(default_factory=list)


class AiFeatureAvailabilityGroup(BaseModel):
    available: list[AiFeatureLabel] = Field(default_factory=list)
    unavailable: list[AiFeatureLabel] = Field(default_factory=list)


class SubscriptionTierCatalogItem(BaseModel):
    """One tier with feature lists available on that tier vs not."""

    id: str
    slug: str
    name: str
    description: str = ""
    display_order: int = 0
    entitlements: dict[str, Any] = Field(default_factory=dict)
    included_ai_features: list[str] = Field(default_factory=list)
    is_custom: bool = False
    is_active: bool = True
    billing_unit_hint: str | None = None
    free_features: ServiceFeatureAvailabilityGroup = Field(
        default_factory=ServiceFeatureAvailabilityGroup
    )
    paid_non_ai_features: ServiceFeatureAvailabilityGroup = Field(
        default_factory=ServiceFeatureAvailabilityGroup
    )
    paid_ai_features: AiFeatureAvailabilityGroup = Field(
        default_factory=AiFeatureAvailabilityGroup
    )


class SubscriptionTierListResponse(BaseModel):
    items: list[SubscriptionTierCatalogItem]
    total: int | None = None
    page: int = 1
    limit: int = 20
