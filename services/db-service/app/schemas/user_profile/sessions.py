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
    """Request model to create a session record."""

    user_id: UUID4 = Field(..., description="User this session belongs to")
    device_name: Optional[str] = Field(
        None, description="Device name from User-Agent"
    )
    ip_address: Optional[str] = Field(None, description="Client IP address")
    last_active_at: datetime = Field(
        ..., description="Session creation / last active time"
    )
    expires_at: datetime = Field(..., description="Session expiry time")
    is_2fa_verified: bool = Field(
        False, description="Whether 2FA was completed"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class CreateResponse(BaseModel):
    """Response model for session creation."""

    id: UUID4 = Field(..., description="Session ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class UpdateRequest(BaseModel):
    """Request model to update a session (patch)."""

    last_active_at: Optional[datetime] = Field(
        None, description="Updated last active time"
    )
    is_2fa_verified: Optional[bool] = Field(
        None, description="2FA verification status"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """Response model for session update."""

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """Response model for session soft delete."""

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config


class GetResponse(SharedModel):
    """Response model for a single session record."""

    user_id: UUID4 = Field(..., description="User this session belongs to")
    device_name: Optional[str] = Field(None, description="Device name")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    last_active_at: datetime = Field(..., description="Last active time")
    expires_at: datetime = Field(..., description="Expiry time")
    is_2fa_verified: bool = Field(
        False, description="Whether 2FA was completed"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None


class SearchRequest(BaseSearchRequest):
    """Request model to search sessions."""

    user_id: Optional[UUID4] = Field(None, description="Filter by user ID")
    ip_address: Optional[str] = Field(None, description="Filter by IP address")
    is_2fa_verified: Optional[bool] = Field(
        None, description="Filter by 2FA status"
    )
    last_active_after: Optional[datetime] = Field(
        None, description="Filter sessions active after this datetime"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None


class ListResponse(BaseListResponse):
    """Response model for session list/search."""

    items: List[GetResponse] = Field(
        ..., description="List of session records"
    )
