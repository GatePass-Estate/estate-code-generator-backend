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


class GuestBase(BaseModel):
    """
    Base guest model containing common fields.

    Attributes:
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        relationship (str): Relationship with guest.
    """

    resident_id: UUID4 = Field(..., description="Resident who saved the guest")

    guest_name: str = Field(..., description="Full name of the guest")

    guest_phone_number: str | None = Field(
        None, description="Phone number of the guest"
    )

    relationship: str = Field(..., description="Relationship with guest")

    @field_serializer("resident_id")
    def serialize_resident_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class CreateRequest(GuestBase):
    """
    Base request model to CREATE a guest record.

    Attributes:
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        relationship (str): Relationship with guest.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created guest.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created guest"
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
        id (UUID): Unique identifier for each guest.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        relationship (str): Relationship with guest.
    """

    resident_id: UUID4 | None = Field(
        default=None, description="Resident who saved the guest"
    )

    guest_name: str | None = Field(
        default=None, description="Full name of the guest"
    )

    guest_phone_number: str | None = Field(
        default=None, description="Phone number of the guest"
    )

    relationship: str | None = Field(
        default=None, description="Relationship with guest"
    )

    @field_serializer("resident_id")
    def serialize_resident_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for the updated guest.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Whether the guest was deleted (soft delete).
        deleted_at: UTC Time when the guest was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, GuestBase):
    """
    Base response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for each guest.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        relationship (str): Relationship with guest.
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
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        relationship (str): Relationship with guest.
    """

    guest_name: Optional[str] = Field(
        None, description="Full name of the guest"
    )
    guest_phone_number: Optional[str] = Field(
        None, description="Phone number of the guest"
    )
    relationship: Optional[str] = Field(
        None, description="Relationship with guest"
    )
    resident_id: Optional[UUID4] = Field(
        None, description="Resident who saved the guest"
    )


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of guests.
        page: Current page number.
        limit: Number of items per page.
        items: List of guest records.
    """

    items: List[GetResponse] = Field(..., description="List of guest records")
