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
    "RatingSample",
    "RatingSummaryItem",
    "RatingSummaryResponse",
]


class AiMarketplaceFeatureRatingBase(BaseModel):
    """Base fields for the resource."""

    ai_marketplace_feature_id: UUID4 = Field(
        ..., description="Parent marketplace feature ID"
    )
    user_id: UUID4 = Field(..., description="Rater user ID")
    score: int = Field(..., ge=1, le=5, description="Score from 1 to 5")
    comment: str | None = Field(None, description="Optional user comment")

    @field_serializer("ai_marketplace_feature_id")
    def serialize_feature_id(self, value):
        """Serialize the parent feature id as a string."""
        return str(value) if value else None

    @field_serializer("user_id")
    def serialize_user_id(self, value):
        """Serialize the rater user id as a string."""
        return str(value) if value else None

    model_config = model_config


class CreateRequest(AiMarketplaceFeatureRatingBase):
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

    score: int | None = Field(
        default=None, ge=1, le=5, description="Score from 1 to 5"
    )
    comment: str | None = Field(
        default=None, description="Optional user comment"
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


class GetResponse(SharedModel, AiMarketplaceFeatureRatingBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    ai_marketplace_feature_id: Optional[UUID4] = Field(
        None, description="Parent marketplace feature ID"
    )
    user_id: Optional[UUID4] = Field(None, description="Rater user ID")
    score: Optional[int] = Field(None, ge=1, le=5, description="Score")


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")


class RatingSample(BaseModel):
    """Bounded sample row for a score level."""

    user_id: str
    score: int
    comment: str | None = None
    created_at: datetime | None = None

    model_config = model_config


class RatingSummaryItem(BaseModel):
    """Average plus up to 5 samples per score for one feature."""

    ai_marketplace_feature_id: str
    rating: float | None = None
    rating_count: int = 0
    samples: dict[str, list[RatingSample]] = Field(default_factory=dict)


class RatingSummaryResponse(BaseModel):
    """Batch rating summaries keyed by parent feature."""

    items: list[RatingSummaryItem] = Field(default_factory=list)
