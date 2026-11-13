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
    """Request model to create a trusted device record."""

    user_id: UUID4 = Field(..., description="User this device belongs to")
    token_hash: str = Field(
        ..., description="SHA-256 hex hash of the device token"
    )
    device_label: Optional[str] = Field(
        None, description="Human-readable device name"
    )
    ip_address: Optional[str] = Field(
        None, description="Client IP at token creation"
    )
    last_seen_at: datetime = Field(
        ..., description="Last time this device was used"
    )
    expires_at: datetime = Field(..., description="Fixed token expiry time")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class CreateResponse(BaseModel):
    """Response model for trusted device creation."""

    id: UUID4 = Field(..., description="Trusted device ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class UpdateRequest(BaseModel):
    """Request model to update a trusted device (patch)."""

    last_seen_at: Optional[datetime] = Field(
        None, description="Updated last seen time"
    )
    is_revoked: Optional[bool] = Field(
        None, description="Whether the device is revoked"
    )
    revoked_at: Optional[datetime] = Field(
        None, description="When the device was revoked"
    )
    device_label: Optional[str] = Field(
        None, description="Updated device label"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """Response model for trusted device update."""

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """Response model for trusted device soft delete."""

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config


class GetResponse(SharedModel):
    """Response model for a single trusted device record."""

    user_id: UUID4 = Field(..., description="User this device belongs to")
    token_hash: str = Field(
        ..., description="SHA-256 hex hash of the device token"
    )
    device_label: Optional[str] = Field(
        None, description="Human-readable device name"
    )
    ip_address: Optional[str] = Field(
        None, description="Client IP at token creation"
    )
    last_seen_at: datetime = Field(
        ..., description="Last time this device was used"
    )
    expires_at: datetime = Field(..., description="Fixed token expiry time")
    is_revoked: bool = Field(
        False, description="Whether the device is revoked"
    )
    revoked_at: Optional[datetime] = Field(
        None, description="When the device was revoked"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None


class SearchRequest(BaseSearchRequest):
    """Request model to search trusted devices."""

    user_id: Optional[UUID4] = Field(None, description="Filter by user ID")
    token_hash: Optional[str] = Field(None, description="Filter by token hash")
    is_revoked: Optional[bool] = Field(
        None, description="Filter by revocation status"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value) if value else None


class ListResponse(BaseListResponse):
    """Response model for trusted device list/search."""

    items: List[GetResponse] = Field(
        ..., description="List of trusted device records"
    )
