from datetime import datetime
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
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class PaymentTransactionBase(BaseModel):
    """Base fields for the resource."""

    estate_id: UUID4 = Field(..., description="Estate ID")
    checkout_session_id: UUID4 | None = Field(
        None, description="Checkout session FK"
    )
    amount: Decimal = Field(..., description="Transaction amount")
    currency_code: str = Field(..., description="Currency code")
    status: str = Field(..., description="Transaction status")
    provider_reference: str | None = Field(
        None, description="Provider reference"
    )
    raw: dict | None = Field(None, description="Raw provider payload")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
        return str(value) if value else None

    @field_serializer("checkout_session_id")
    def serialize_checkout_session_id(self, value):
        return str(value) if value else None

    model_config = model_config


class CreateRequest(PaymentTransactionBase):
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
    checkout_session_id: UUID4 | None = Field(
        default=None, description="Checkout session FK"
    )
    amount: Decimal | None = Field(
        default=None, description="Transaction amount"
    )
    currency_code: str | None = Field(
        default=None, description="Currency code"
    )
    status: str | None = Field(default=None, description="Transaction status")
    provider_reference: str | None = Field(
        default=None, description="Provider reference"
    )
    raw: dict | None = Field(default=None, description="Raw provider payload")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value):
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


class GetResponse(SharedModel, PaymentTransactionBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    estate_id: Optional[UUID4] = Field(None, description="Estate ID")
    checkout_session_id: UUID4 | None = Field(
        None, description="Checkout session FK"
    )
    currency_code: Optional[str] = Field(None, description="Currency code")
    status: Optional[str] = Field(None, description="Transaction status")
    provider_reference: str | None = Field(
        None, description="Provider reference"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
