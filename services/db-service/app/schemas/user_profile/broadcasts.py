from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "Audience",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class Audience(str, Enum):
    """
    Audience for the broadcast
    """

    ALL = "all"
    ROOT = "root"
    PRIMARY_ADMIN = "primary_admin"
    ADMIN = "admin"
    RESIDENT = "resident"
    SECURITY = "security"
    GUEST = "guest"


class BroadcastBase(BaseModel):
    """
    Base broadcast model containing common fields.

    Attributes:
        estate_id (UUID): Broadcast estate.
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full Broadcast message.
        audience (Audience): Audience for the broadcast.
        attachment_url (str): Optional URL of the attachment.
        status (bool): Active/inactive status.
        expires_at (DateTime): UTC timestamp of expiration.
    """

    estate_id: UUID4 | None = Field(None, description="Broadcast estate")
    sender_id: UUID4 = Field(..., description="User who created the broadcast")

    title: str = Field(..., description="Broadcast title")
    message: str = Field(..., description="Full Broadcast message")

    audience: Audience = Field(..., description="Audience for the broadcast")
    attachment_url: str | None = Field(
        None, description="Optional URL of the attachment"
    )
    status: bool = Field(..., description="Active/inactive status")
    expires_at: datetime | None = Field(
        None, description="UTC timestamp of expiration"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value) if value else None

    @field_serializer("sender_id")
    def serialize_sender_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class CreateRequest(BroadcastBase):
    """
    Base request model to CREATE a broadcast record.

    Attributes:
        estate_id (UUID): Broadcast estate.
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full Broadcast message.
        audience (Audience): Audience for the broadcast.
        attachment_url (str): Optional URL of the attachment.
        status (bool): Active/inactive status.
        expires_at (DateTime): UTC timestamp of expiration.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created broadcast.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created broadcast"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """
    Base request model to UPDATE a record. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        id (UUID): Unique identifier for each broadcast.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        estate_id (UUID): Broadcast estate.
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full Broadcast message.
        audience (Audience): Audience for the broadcast.
        attachment_url (str): Optional URL of the attachment.
        status (bool): Active/inactive status.
        expires_at (DateTime): UTC timestamp of expiration.
    """

    estate_id: UUID4 | None = Field(
        default=None, description="Broadcast estate"
    )
    sender_id: UUID4 | None = Field(
        default=None, description="User who created the broadcast"
    )

    title: str | None = Field(default=None, description="Broadcast title")
    message: str | None = Field(
        default=None, description="Full Broadcast message"
    )

    audience: Audience | None = Field(
        default=None, description="Audience for the broadcast"
    )
    attachment_url: str | None = Field(
        default=None, description="Optional URL of the attachment"
    )
    status: bool | None = Field(
        default=None, description="Active/inactive status"
    )
    expires_at: datetime | None = Field(
        default=None, description="UTC timestamp of expiration"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value) if value else None

    @field_serializer("sender_id")
    def serialize_sender_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for the updated broadcast.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Whether the broadcast was deleted (soft delete).
        deleted_at: UTC Time when the broadcast was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, BroadcastBase):
    """
    Base response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for each broadcast.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        estate_id (UUID): Broadcast estate.
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full Broadcast message.
        audience (Audience): Audience for the broadcast.
        attachment_url (str): Optional URL of the attachment.
        status (bool): Active/inactive status.
        expires_at (DateTime): UTC timestamp of expiration.
    """


class SearchRequest(BaseSearchRequest):
    """
    Request model to GET a list of items that are not archived and filtered
    according to the provided contraints. Items are returned in a chronological
    order based on the creation timestamp.

    Attributes:
        from_date: Filter by creation date (from)
        to_date: Filter by creation date (to)
        page: Page number for pagination
        limit: Number of items per page
        estate_id (UUID): Broadcast estate.
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full Broadcast message.
        audience (Audience): Audience for the broadcast.
        attachment_url (str): Optional URL of the attachment.
        status (bool): Active/inactive status.
        expires_at (DateTime): UTC timestamp of expiration.
    """

    estate_id: Optional[UUID4] = Field(
        default=None, description="Broadcast estate"
    )
    sender_id: Optional[UUID4] = Field(
        default=None, description="User who created the broadcast"
    )

    title: Optional[str] = Field(default=None, description="Broadcast title")
    message: Optional[str] = Field(
        default=None, description="Full Broadcast message"
    )

    audience: Optional[Audience] = Field(
        default=None, description="Audience for the broadcast"
    )
    attachment_url: Optional[str] = Field(
        default=None, description="Optional URL of the attachment"
    )
    status: Optional[bool] = Field(
        default=None, description="Active/inactive status"
    )
    expires_at: Optional[datetime] = Field(
        default=None, description="UTC timestamp of expiration"
    )


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of broadcasts.
        page: Current page number.
        limit: Number of items per page.
        items: List of broadcast records.
    """

    items: List[GetResponse] = Field(
        ..., description="List of broadcast records"
    )
