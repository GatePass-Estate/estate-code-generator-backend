from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import BaseListResponse, SharedModel, model_config

__all__ = [
    "CreateRequest",
    "CreateResponse",
    "DismissRequest",
    "DismissAllRequest",
    "GetResponse",
    "ListResponse",
    "SearchRequest",
]


class CreateRequest(BaseModel):
    """Request model to mark a broadcast as read."""

    broadcast_id: UUID4 = Field(..., description="Broadcast being marked read")
    user_id: UUID4 = Field(..., description="User marking the broadcast read")

    @field_serializer("broadcast_id")
    def serialize_broadcast_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class CreateResponse(BaseModel):
    """Response after marking a broadcast as read."""

    id: UUID4 = Field(..., description="Broadcast read record ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class DismissRequest(BaseModel):
    """Request model to dismiss a single broadcast for a user."""

    broadcast_id: UUID4 = Field(..., description="Broadcast to dismiss")
    user_id: UUID4 = Field(..., description="User dismissing the broadcast")

    @field_serializer("broadcast_id")
    def serialize_broadcast_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class DismissAllRequest(BaseModel):
    """Request model to dismiss all BROADCAST-category broadcasts for a user."""

    user_id: UUID4 = Field(..., description="User dismissing all broadcasts")
    estate_id: UUID4 = Field(..., description="Estate scope for dismissal")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class GetResponse(SharedModel):
    """Full broadcast read record."""

    broadcast_id: UUID4 = Field(..., description="Broadcast ID")
    user_id: UUID4 = Field(..., description="User ID")
    read_at: datetime = Field(..., description="When the broadcast was read")
    is_dismissed: bool = Field(
        False, description="Whether the user dismissed this broadcast"
    )

    @field_serializer("broadcast_id")
    def serialize_broadcast_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)


class SearchRequest(BaseModel):
    """Filter parameters for listing broadcast read records."""

    broadcast_id: Optional[UUID4] = Field(
        default=None, description="Filter by broadcast"
    )
    user_id: Optional[UUID4] = Field(
        default=None, description="Filter by user"
    )
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

    model_config = model_config


class ListResponse(BaseListResponse):
    """Paginated list of broadcast read records."""

    items: List[GetResponse] = Field(
        ..., description="List of broadcast read records"
    )
