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


class CreateRequest(BaseModel):
    """Request model to store a hashed recovery code."""

    user_id: UUID4 = Field(..., description="User this code belongs to")
    code_hash: str = Field(..., description="Bcrypt hash of the recovery code")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class CreateResponse(BaseModel):
    """Response model for recovery code creation."""

    id: UUID4 = Field(..., description="Record ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class UpdateRequest(BaseModel):
    """Request model to mark a recovery code as used."""

    used_at: Optional[datetime] = Field(
        None, description="Time the code was consumed"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """Response model for recovery code update."""

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """Response model for recovery code soft delete."""

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config


class GetResponse(SharedModel):
    """Response model for a single recovery code record."""

    user_id: UUID4 = Field(..., description="User this code belongs to")
    code_hash: str = Field(..., description="Bcrypt hash of the code")
    used_at: Optional[datetime] = Field(
        None, description="When consumed (null = unused)"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None


class SearchRequest(BaseSearchRequest):
    """Request model to search recovery codes."""

    user_id: Optional[UUID4] = Field(None, description="Filter by user ID")
    is_used: Optional[bool] = Field(None, description="Filter by used status")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None


class ListResponse(BaseListResponse):
    """Response model for recovery code list/search."""

    items: List[GetResponse] = Field(
        ..., description="List of recovery code records"
    )
