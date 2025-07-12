from datetime import datetime
from pydantic import (
    BaseModel,
    Field,
    UUID4,
    ConfigDict,
    field_serializer,
)
from typing import List, Optional

__all__ = [
    "RegisterGuestRequest",
    "RegisterGuestResponse",
    "UpdateGuestRequest",
    "UpdateGuestResponse",
    "GetGuestResponse",
    "DeleteGuestResponse",
    "SearchGuestRequest",
    "ListGuestResponse",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class RegisterGuestRequest(BaseModel):
    """
    Request model to register a new guest.

    Attributes:
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        guest_gender (str): Gender of the guest.
        relationship (str): Relationship with guest.
    """

    resident_id: UUID4 = Field(..., description="Resident who saved the guest")

    guest_name: str = Field(
        ..., min_length=1, description="Full name of the guest"
    )

    guest_phone_number: Optional[str] = Field(
        None, description="Phone number of the guest"
    )

    guest_gender: Optional[str] = Field(
        None, description="Gender of the guest"
    )

    relationship: str = Field(..., description="Relationship with guest")

    @field_serializer("resident_id")
    def serialize_resident_id(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class RegisterGuestResponse(BaseModel):
    """
    Response model after registering a guest.

    Attributes:
        id (UUID4): Registered Guest ID.
        created_at (datetime): Guest creation timestamp.
    """

    id: UUID4 = Field(..., description="Registered guest ID")
    created_at: datetime = Field(..., description="Guest creation timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class UpdateGuestRequest(BaseModel):
    """
    Request model to update guest information.
    All fields are optional - only provided fields will be updated.

    Attributes:
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        guest_gender (str): Gender of the guest.
        relationship (str): Relationship with guest.
    """

    guest_name: Optional[str] = Field(
        None, description="Full name of guest", min_length=1
    )
    guest_phone_number: Optional[str] = Field(
        None, description="Guest's phone number"
    )
    guest_gender: Optional[str] = Field(
        None, description="Gender of the guest"
    )
    relationship: Optional[str] = Field(
        None, description="Relationship with guest", min_length=1
    )

    model_config = model_config


class UpdateGuestResponse(BaseModel):
    """
    Response model for guest update operations.

    Attributes:
        id (UUID4): Guest ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID4 = Field(..., description="Guest ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class GetGuestResponse(BaseModel):
    """
    Response model to get a guest by ID.

    Attributes:
        id (UUID): Unique identifier for each guest.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        guest_gender (str): Optional Guest Gender.
        relationship (str): Relationship with guest.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        is_deleted (bool): Deletion status.
    """

    id: UUID4 = Field(..., description="Guest ID")
    resident_id: UUID4 = Field(..., description="Resident ID")
    guest_name: str = Field(..., description="Guest name")
    guest_gender: Optional[str] = Field(..., description="Guest's gender")
    guest_phone_number: Optional[str] = Field(
        None, description="Guest's phone number"
    )
    relationship: str = Field(..., description="Relationship with Guest")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(
        None, description="Last update timestamp"
    )
    is_deleted: bool = Field(False, description="Deletion status")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class DeleteGuestResponse(BaseModel):
    """
    Response model for guest deletion (soft delete).

    Attributes:
        is_deleted (bool): Whether the guest was deleted (soft delete).
        deleted_at (datetime): UTC Time when the guest was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config


class SearchGuestRequest(BaseModel):
    """
    Request model to search guests with optional filters and pagination.

    Attributes:
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        guest_gender (str): Gender of Guest.
        relationship (str): Relationship with guest.
        from_date (datetime): Filter by creation date (from).
        to_date (datetime): Filter by creation date (to).
        page (int): Page number for pagination.
        limit (int): Number of items per page.
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
    guest_gender: Optional[str] = Field(None, description="Gender of guest")
    from_date: Optional[datetime] = Field(
        None, description="Filter by creation date (from)"
    )
    to_date: Optional[datetime] = Field(
        None, description="Filter by creation date (to)"
    )
    page: int = Field(1, ge=1, description="Page number for pagination")
    limit: int = Field(
        10, ge=1, le=100, description="Number of items per page"
    )

    model_config = model_config


class ListGuestResponse(BaseModel):
    """
    Response model for guest list/search operations.

    Attributes:
        total (int): Total number of guests matching search criteria.
        page (int): Current page number.
        limit (int): Number of items per page.
        items (List[GetGuestResponse]): List of guest records.
    """

    total: int = Field(..., description="Total number of guests")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[GetGuestResponse] = Field(..., description="List of guests")

    model_config = model_config
