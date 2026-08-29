from datetime import datetime
from typing import Any, List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer, field_validator

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


class AiMarketplaceFeatureBase(BaseModel):
    """Base fields for the resource."""

    name: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Product overview")
    category: str = Field(..., description="Marketplace category")
    is_active: bool = Field(
        default=True, description="Whether product is active"
    )
    tiers: Any = Field(
        default_factory=list,
        description="Child ai_feature tiers, e.g. "
        "[{tier, ai_feature_id}, ...]",
    )

    model_config = model_config


class CreateRequest(AiMarketplaceFeatureBase):
    """Request model to CREATE a record."""


class CreateResponse(BaseModel):
    """Response model to CREATE a record."""

    id: UUID4 = Field(..., description="Unique identifier")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        """Serialize the record id as a string."""
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """Request model to UPDATE a record. All fields optional."""

    name: str | None = Field(default=None, description="Display name")
    description: str | None = Field(
        default=None, description="Product overview"
    )
    category: str | None = Field(
        default=None, description="Marketplace category"
    )
    is_active: bool | None = Field(
        default=None, description="Whether product is active"
    )
    tiers: Any | None = Field(
        default=None, description="Child ai_feature tiers"
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


class GetResponse(SharedModel, AiMarketplaceFeatureBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    name: Optional[str] = Field(None, description="Display name")
    category: Optional[List[str]] = Field(
        None, description="Marketplace categories"
    )
    is_active: Optional[bool] = Field(
        None, description="Whether product is active"
    )

    @field_validator("category", mode="before")
    @classmethod
    def _category_as_list(cls, value):
        """Coerce a single category string into a one-item list."""
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return [value]
        return value


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
