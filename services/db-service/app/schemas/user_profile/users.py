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
    "UserRole",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class UserRole(str, Enum):
    """
    Enumeration of supported user roles: root, primary_admin, admin, resident,
                security, guest
    """

    ROOT = "root"
    PRIMARY_ADMIN = "primary_admin"
    ADMIN = "admin"
    RESIDENT = "resident"
    SECURITY = "security"
    GUEST = "guest"


class UserBase(BaseModel):
    """
    Base user model containing common fields.

    Attributes:
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email address of the user.
        phone_number (str): Optional phone number.
        home_address (str): Home address.
        password (str): Hashed password.
        estate_id (UUID): Reference to the estate.
        household_id (UUID): Reference to the household.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
    """

    first_name: str = Field(..., description="First name of the user")

    last_name: str = Field(..., description="Last name of the user")

    email: str = Field(..., description="Unique email address of the user")

    phone_number: str | None = Field(
        None, description="Phone number of the user"
    )

    home_address: str = Field(..., description="Home address")

    password: str = Field(..., description="Hashed password")

    estate_id: UUID4 | None = Field(
        default=None, description="Estate the user is registered to"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value) if value else None

    household_id: UUID4 | None = Field(
        default=None, description="Household the user is registered to"
    )

    @field_serializer("household_id")
    def serialize_household_id(self, value: UUID4) -> str:
        return str(value) if value else None

    role: UserRole = Field(..., description="Role assigned to the user")

    status: bool = Field(default=True, description="Active/inactive status")

    model_config = model_config


class CreateRequest(UserBase):
    """
    Base request model to CREATE a user record.

    Attributes:
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email address of the user.
        phone_number (str): Optional phone number.
        home_address (str): Home address.
        password (str): Hashed password.
        estate_id (UUID): Reference to the estate.
        household_id (UUID): Reference to the household.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created user.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created user"
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
        id (UUID): Unique identifier for each user.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email for authentication.
        phone_number (str): Optional phone number.
        home_address (str): Home address.
        password (str): Hashed password.
        estate_id (UUID): Reference to the estate.
        household_id (UUID): Reference to the household.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
    """

    first_name: str | None = Field(
        default=None, description="First name of the user"
    )
    last_name: str | None = Field(
        default=None, description="Last name of the user"
    )
    email: str | None = Field(default=None, description="Unique email address")
    phone_number: str | None = Field(
        default=None, description="Phone number of the user"
    )
    home_address: str | None = Field(default=None, description="Home address")
    password: str | None = Field(default=None, description="Hashed password")
    estate_id: UUID4 | None = Field(
        default=None, description="Estate the user is registered to"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value) if value else None

    household_id: UUID4 | None = Field(
        default=None, description="Household the user is registered to"
    )

    @field_serializer("household_id")
    def serialize_household_id(self, value: UUID4) -> str:
        return str(value) if value else None

    role: UserRole | None = Field(
        default=None, description="Role assigned to the user"
    )
    status: bool | None = Field(
        default=None, description="Active/inactive status"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for the updated user.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Whether the user was deleted (soft delete).
        deleted_at: UTC Time when the user was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, UserBase):
    """
    Base response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for each user.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email for authentication.
        phone_number (str): Optional phone number.
        home_address (str): Home address.
        password (str): Hashed password.
        estate_id (UUID): Reference to the estate.
        household_id (UUID): Reference to the household.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
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
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email for authentication.
        phone_number (str): Optional phone number.
        home_address (str): Home address.
        estate_id (UUID): Reference to the estate.
        household_id (UUID): Reference to the household.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
    """

    first_name: Optional[str] = Field(
        None, description="First name of the user"
    )
    last_name: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(None, description="Email of the user")
    phone_number: Optional[str] = Field(
        None, description="Phone number of the user"
    )
    home_address: Optional[str] = Field(None, description="Home address")
    estate_id: Optional[UUID4] = Field(
        None, description="Reference to the estate"
    )
    household_id: Optional[UUID4] = Field(
        None, description="Reference to the household"
    )
    role: Optional[UserRole] = Field(None, description="User role")
    status: Optional[bool] = Field(None, description="Active/inactive status")


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of users.
        page: Current page number.
        limit: Number of items per page.
        items: List of user records.
    """

    items: List[GetResponse] = Field(..., description="List of user records")
