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
    "SubscriptionStatus",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class SubscriptionStatus(str, Enum):
    """Enumeration for SubscriptionStatus."""

    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class EstateSubscriptionBase(BaseModel):
    """Base fields for the resource."""

    estate_id: UUID4 = Field(..., description="Estate ID")
    tier_id: UUID4 = Field(..., description="Subscription tier ID")
    status: SubscriptionStatus = Field(..., description="Subscription status")
    period_start: datetime = Field(..., description="Period start")
    period_end: datetime = Field(..., description="Period end")
    auto_renew: bool = Field(default=True, description="Auto renew flag")
    covered_users: int = Field(default=1, description="Seat count")
    over_cap_locked: bool = Field(
        default=False,
        description="True when estate exceeds Access seat cap after expiry",
    )
    entitlements: dict | None = Field(
        None, description="Custom entitlements snapshot"
    )
    paystack_subscription_code: str | None = Field(
        None, description="Paystack subscription code"
    )
    paystack_customer_code: str | None = Field(
        None, description="Paystack customer code"
    )
    renew_attempt_count: int = Field(
        default=0, description="Consecutive renewal attempt count"
    )
    last_renewal_failure_at: datetime | None = Field(
        None, description="Last renewal failure time"
    )
    last_renewal_failure_reason: str | None = Field(
        None, description="Last renewal failure reason"
    )
    cancelled_at: datetime | None = Field(None, description="Cancelled at")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    @field_serializer("tier_id")
    def serialize_tier_id(self, value):
        return str(value) if value else None

    model_config = model_config


class CreateRequest(EstateSubscriptionBase):
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
    tier_id: UUID4 | None = Field(
        default=None, description="Subscription tier ID"
    )
    status: SubscriptionStatus | None = Field(
        default=None, description="Subscription status"
    )
    period_start: datetime | None = Field(
        default=None, description="Period start"
    )
    period_end: datetime | None = Field(default=None, description="Period end")
    auto_renew: bool | None = Field(
        default=None, description="Auto renew flag"
    )
    covered_users: int | None = Field(default=None, description="Seat count")
    over_cap_locked: bool | None = Field(
        default=None,
        description="True when estate exceeds Access seat cap after expiry",
    )
    entitlements: dict | None = Field(
        default=None, description="Custom entitlements snapshot"
    )
    paystack_subscription_code: str | None = Field(
        default=None, description="Paystack subscription code"
    )
    paystack_customer_code: str | None = Field(
        default=None, description="Paystack customer code"
    )
    renew_attempt_count: int | None = Field(
        default=None, description="Consecutive renewal attempt count"
    )
    last_renewal_failure_at: datetime | None = Field(
        default=None, description="Last renewal failure time"
    )
    last_renewal_failure_reason: str | None = Field(
        default=None, description="Last renewal failure reason"
    )
    cancelled_at: datetime | None = Field(
        default=None, description="Cancelled at"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    @field_serializer("tier_id")
    def serialize_tier_id(self, value):
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


class GetResponse(SharedModel, EstateSubscriptionBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    estate_id: Optional[UUID4] = Field(None, description="Estate ID")
    tier_id: Optional[UUID4] = Field(None, description="Subscription tier ID")
    status: Optional[SubscriptionStatus] = Field(
        None, description="Subscription status"
    )
    paystack_subscription_code: Optional[str] = Field(
        None, description="Paystack subscription code"
    )
    paystack_customer_code: Optional[str] = Field(
        None, description="Paystack customer code"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
