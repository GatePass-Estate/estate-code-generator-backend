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


class SubscriptionTierBase(BaseModel):
    """Base fields for the resource."""

    slug: str = Field(..., description="Unique tier slug")
    name: str = Field(..., description="Display name")
    display_order: int = Field(default=0, description="UI ordering")
    entitlements: dict = Field(
        default_factory=dict, description="Entitlements JSONB map"
    )
    included_ai_features: List[str] = Field(
        default_factory=list, description="Bundled AI feature keys"
    )
    is_custom: bool = Field(
        default=False, description="Enterprise/custom tier"
    )
    is_active: bool = Field(default=True, description="Whether tier is active")
    billing_unit_hint: str | None = Field(
        None, description="residential|institution"
    )

    model_config = model_config


class CreateRequest(SubscriptionTierBase):
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

    slug: str | None = Field(default=None, description="Unique tier slug")
    name: str | None = Field(default=None, description="Display name")
    display_order: int | None = Field(default=None, description="UI ordering")
    entitlements: dict | None = Field(
        default=None, description="Entitlements JSONB map"
    )
    included_ai_features: List[str] | None = Field(
        default=None, description="Bundled AI feature keys"
    )
    is_custom: bool | None = Field(
        default=None, description="Enterprise/custom tier"
    )
    is_active: bool | None = Field(
        default=None, description="Whether tier is active"
    )
    billing_unit_hint: str | None = Field(
        default=None, description="residential|institution"
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


class GetResponse(SharedModel, SubscriptionTierBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    slug: Optional[str] = Field(None, description="Unique tier slug")
    name: Optional[str] = Field(None, description="Display name")
    is_custom: Optional[bool] = Field(
        None, description="Enterprise/custom tier"
    )
    is_active: Optional[bool] = Field(
        None, description="Whether tier is active"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
