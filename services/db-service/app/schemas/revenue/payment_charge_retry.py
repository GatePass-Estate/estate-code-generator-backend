from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class PaymentChargeRetryBase(BaseModel):
    """Base fields for the resource."""

    estate_id: UUID4 = Field(..., description="Estate ID")
    target_type: str = Field(
        ..., description="Target type (estate_subscription or ai_grant)"
    )
    target_id: UUID4 = Field(..., description="Target entity ID")
    paystack_subscription_code: str = Field(
        ..., description="Paystack subscription code"
    )
    billing_period_key: str = Field(
        ..., description="Idempotency key for billing period"
    )
    amount_kobo: int = Field(..., description="Charge amount in kobo")
    currency_code: str = Field("NGN", description="Currency code")
    authorization_code: str = Field(
        ..., description="Paystack authorization code"
    )
    customer_email: str = Field(..., description="Customer email")
    status: str = Field("pending", description="Retry status")
    attempt_number: int = Field(0, description="Current attempt number")
    max_attempts: int = Field(..., description="Maximum retry attempts")
    next_retry_at: datetime | None = Field(
        None, description="Next scheduled retry"
    )
    last_attempted_at: datetime | None = Field(
        None, description="Last attempt timestamp"
    )
    last_gateway_response: str | None = Field(
        None, description="Last Paystack gateway response"
    )
    last_provider_reference: str | None = Field(
        None, description="Last Paystack transaction reference"
    )
    resolved_at: datetime | None = Field(
        None, description="When retry was resolved"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    @field_serializer("target_id")
    def serialize_target_id(self, value):
        return str(value) if value else None

    model_config = model_config


class CreateRequest(PaymentChargeRetryBase):
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

    status: str | None = Field(default=None, description="Retry status")
    attempt_number: int | None = Field(
        default=None, description="Current attempt number"
    )
    next_retry_at: datetime | None = Field(
        default=None, description="Next scheduled retry"
    )
    last_attempted_at: datetime | None = Field(
        default=None, description="Last attempt timestamp"
    )
    last_gateway_response: str | None = Field(
        default=None, description="Last Paystack gateway response"
    )
    last_provider_reference: str | None = Field(
        default=None, description="Last Paystack transaction reference"
    )
    resolved_at: datetime | None = Field(
        default=None, description="When retry was resolved"
    )

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


class GetResponse(SharedModel, PaymentChargeRetryBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    estate_id: Optional[UUID4] = Field(None, description="Estate ID")
    target_type: Optional[str] = Field(None, description="Target type")
    target_id: Optional[UUID4] = Field(None, description="Target entity ID")
    status: Optional[str] = Field(None, description="Retry status")
    billing_period_key: Optional[str] = Field(
        None, description="Billing period key"
    )
    next_retry_at_before: Optional[datetime] = Field(
        None, description="Retries due before this timestamp"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
