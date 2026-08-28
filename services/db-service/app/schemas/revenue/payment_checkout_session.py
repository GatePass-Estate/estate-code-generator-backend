from datetime import datetime
from enum import Enum
from typing import List, Optional
from decimal import Decimal

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "CheckoutStatus",
    "CheckoutKind",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class CheckoutStatus(str, Enum):
    """Enumeration for CheckoutStatus."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"


class CheckoutKind(str, Enum):
    """Enumeration for CheckoutKind."""

    TIER = "tier"
    CUSTOM = "custom"
    SEAT_ADD = "seat_add"
    AI_ONLY = "ai_only"


class PaymentCheckoutSessionBase(BaseModel):
    """Base fields for the resource."""

    estate_id: UUID4 = Field(..., description="Estate ID")
    idempotency_key: str = Field(..., description="Idempotency key")
    paystack_reference: str | None = Field(
        None, description="Paystack reference"
    )
    status: CheckoutStatus = Field(
        default=CheckoutStatus.PENDING, description="Checkout status"
    )
    pricing_snapshot: dict = Field(..., description="Pricing snapshot JSON")
    amount: Decimal = Field(..., description="Charge amount")
    currency_code: str = Field(..., description="Currency code")
    country_code: str = Field(..., description="Country code")
    checkout_kind: CheckoutKind = Field(..., description="Checkout kind")
    session_metadata: dict | None = Field(
        None, description="Optional metadata"
    )
    paid_at: datetime | None = Field(None, description="Paid at")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    model_config = model_config


class CreateRequest(PaymentCheckoutSessionBase):
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
    idempotency_key: str | None = Field(
        default=None, description="Idempotency key"
    )
    paystack_reference: str | None = Field(
        default=None, description="Paystack reference"
    )
    status: CheckoutStatus | None = Field(
        default=None, description="Checkout status"
    )
    pricing_snapshot: dict | None = Field(
        default=None, description="Pricing snapshot JSON"
    )
    amount: Decimal | None = Field(default=None, description="Charge amount")
    currency_code: str | None = Field(
        default=None, description="Currency code"
    )
    country_code: str | None = Field(default=None, description="Country code")
    checkout_kind: CheckoutKind | None = Field(
        default=None, description="Checkout kind"
    )
    session_metadata: dict | None = Field(
        default=None, description="Optional metadata"
    )
    paid_at: datetime | None = Field(default=None, description="Paid at")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
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


class GetResponse(SharedModel, PaymentCheckoutSessionBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    estate_id: Optional[UUID4] = Field(None, description="Estate ID")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key")
    paystack_reference: str | None = Field(
        None, description="Paystack reference"
    )
    status: Optional[CheckoutStatus] = Field(
        None, description="Checkout status"
    )
    currency_code: Optional[str] = Field(None, description="Currency code")
    country_code: Optional[str] = Field(None, description="Country code")
    checkout_kind: Optional[CheckoutKind] = Field(
        None, description="Checkout kind"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
