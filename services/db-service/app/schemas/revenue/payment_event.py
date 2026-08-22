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


class PaymentEventBase(BaseModel):
    """Base fields for the resource."""

    provider: str = Field(default="paystack", description="Payment provider")
    event_id: str = Field(..., description="Provider event id")
    event_type: str = Field(..., description="Event type")
    payload: dict = Field(..., description="Raw event payload")
    processed_at: datetime | None = Field(None, description="Processed at")

    model_config = model_config


class CreateRequest(PaymentEventBase):
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

    provider: str | None = Field(default=None, description="Payment provider")
    event_id: str | None = Field(default=None, description="Provider event id")
    event_type: str | None = Field(default=None, description="Event type")
    payload: dict | None = Field(default=None, description="Raw event payload")
    processed_at: datetime | None = Field(
        default=None, description="Processed at"
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


class GetResponse(SharedModel, PaymentEventBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    provider: Optional[str] = Field(None, description="Payment provider")
    event_id: Optional[str] = Field(None, description="Provider event id")
    event_type: Optional[str] = Field(None, description="Event type")


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
