from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "AiGrantStatus",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class AiGrantStatus(str, Enum):
    """Enumeration for AiGrantStatus."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"


class EstateAiFeatureBase(BaseModel):
    """Base fields for the resource."""

    estate_id: UUID4 = Field(..., description="Estate ID")
    ai_feature_id: UUID4 = Field(..., description="AI feature ID")
    source: str | None = Field(
        None,
        description="subscription_tier|standalone_purchase|trial|admin_grant|free_install",
    )
    estate_subscription_id: UUID4 | None = Field(
        None, description="Linked subscription for tier-bundled grants"
    )
    checkout_session_id: UUID4 | None = Field(
        None, description="Checkout session for standalone AI purchase"
    )
    is_installed: bool = Field(default=True, description="Installed flag")
    status: AiGrantStatus = Field(
        default=AiGrantStatus.ACTIVE, description="Billing grant status"
    )
    is_free: bool = Field(
        default=False, description="Copied from ai_feature.is_free at grant"
    )
    auto_renew: bool = Field(default=True, description="Auto renew flag")
    starts_at: datetime | None = Field(None, description="Grant/install start")
    expires_at: datetime | None = Field(None, description="Expiry timestamp")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    @field_serializer("ai_feature_id")
    def serialize_ai_feature_id(self, value):
        return str(value) if value else None

    @field_serializer("estate_subscription_id")
    def serialize_estate_subscription_id(self, value):
        return str(value) if value else None

    @field_serializer("checkout_session_id")
    def serialize_checkout_session_id(self, value):
        return str(value) if value else None

    model_config = model_config


class CreateRequest(EstateAiFeatureBase):
    """Request model to CREATE a record."""


class CreateResponse(BaseModel):
    """Response model to CREATE a record."""

    id: UUID4 = Field(..., description="Unique identifier")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """Request model to UPDATE a record. All fields optional."""

    estate_id: UUID4 | None = Field(default=None, description="Estate ID")
    ai_feature_id: UUID4 | None = Field(
        default=None, description="AI feature ID"
    )
    source: str | None = Field(default=None, description="Grant source")
    estate_subscription_id: UUID4 | None = Field(
        default=None, description="Linked subscription id"
    )
    checkout_session_id: UUID4 | None = Field(
        default=None, description="Checkout session id"
    )
    is_installed: bool | None = Field(
        default=None, description="Installed flag"
    )
    status: AiGrantStatus | None = Field(
        default=None, description="Grant status"
    )
    is_free: bool | None = Field(default=None, description="Free grant flag")
    auto_renew: bool | None = Field(
        default=None, description="Auto renew flag"
    )
    starts_at: datetime | None = Field(default=None, description="Grant start")
    expires_at: datetime | None = Field(
        default=None, description="Expiry timestamp"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    @field_serializer("ai_feature_id")
    def serialize_ai_feature_id(self, value):
        return str(value) if value else None

    @field_serializer("estate_subscription_id")
    def serialize_estate_subscription_id(self, value):
        return str(value) if value else None

    @field_serializer("checkout_session_id")
    def serialize_checkout_session_id(self, value):
        return str(value) if value else None

    model_config = model_config


class UpdateResponse(CreateResponse):
    """Response model to UPDATE a record."""

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """Response model to DELETE a record."""

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, EstateAiFeatureBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    estate_id: Optional[UUID4] = Field(None, description="Estate ID")
    ai_feature_id: Optional[UUID4] = Field(None, description="AI feature ID")
    is_installed: Optional[bool] = Field(None, description="Installed flag")
    status: Optional[AiGrantStatus] = Field(None, description="Grant status")
    source: str | None = Field(None, description="tier_bundle|standalone")


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
