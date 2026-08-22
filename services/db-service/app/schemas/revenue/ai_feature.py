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


class AiFeatureBase(BaseModel):
    """Base fields for the resource."""

    feature_key: str = Field(..., description="Unique AI feature key")
    name: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Optional description")
    is_free: bool = Field(default=False, description="Free catalog feature")
    is_active: bool = Field(
        default=True, description="Whether feature is active"
    )

    model_config = model_config


class CreateRequest(AiFeatureBase):
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

    feature_key: str | None = Field(
        default=None, description="Unique AI feature key"
    )
    name: str | None = Field(default=None, description="Display name")
    description: str | None = Field(
        default=None, description="Optional description"
    )
    is_free: bool | None = Field(
        default=None, description="Free catalog feature"
    )
    is_active: bool | None = Field(
        default=None, description="Whether feature is active"
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


class GetResponse(SharedModel, AiFeatureBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    feature_key: Optional[str] = Field(
        None, description="Unique AI feature key"
    )
    name: Optional[str] = Field(None, description="Display name")
    is_free: Optional[bool] = Field(None, description="Free catalog feature")
    is_active: Optional[bool] = Field(
        None, description="Whether feature is active"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
