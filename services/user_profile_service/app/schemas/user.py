from enum import Enum
from datetime import datetime
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    UUID4,
    ConfigDict,
    field_serializer,
)
from typing import List, Optional

__all__ = [
    "RegisterUserRequest",
    "RegisterUserResponse",
    "UserProfileRequest",
    "UserProfileResponse",
    "SetPasswordRequest",
    "SetPasswordResponse",
    "UpdatePasswordRequest",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class Role(str, Enum):
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


class Gender(str, Enum):
    """
    Enumeration of supported gender options.
    """

    MALE = "male"
    FEMALE = "female"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class RegisterUserRequest(BaseModel):
    """
    Request model to register a new user.

    Attributes:
        first_name (str): User's first name.
        last_name (str): User's last name
        home_address (str): User's home address.
        email (EmailStr): User's email address.
        phone_number (str): User's phone number.
        gender (Gender): User's gender.
        role (Role): User role.
        estate_id (UUID4): Estate the user belongs to.
        household_id (UUID4): Optional household ID.
    """

    first_name: str = Field(..., min_length=1, description="User's first name")
    last_name: str = Field(..., min_length=1, description="User's last name")
    home_address: str = Field(
        ..., min_length=1, description="User's home address"
    )
    email: EmailStr = Field(..., description="User's email address")
    phone_number: Optional[str] = Field(
        None, description="User's phone number"
    )
    gender: Gender = Field(..., description="User's gender")
    role: Role = Field(..., description="User role")
    estate_id: UUID4 = Field(..., description="Estate the user belongs to")
    household_id: Optional[UUID4] = Field(
        None, description="Optional household ID"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4) -> str:
        return str(estate_id)

    @field_serializer("household_id")
    def serialize_household_id(
        self, household_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(household_id) if household_id else None

    model_config = model_config


class RegisterUserResponse(BaseModel):
    """
    Response model after registering a user.

    Attributes:
        id (UUID4): Registered user ID.
        first_name (str): User's first name.
        last_name (str): User's last name.
        home_address (str): User's home address.
        email (EmailStr): User's email address.
        gender (Gender): User's gender.
        role (Role): Assigned user role.
        estate_id (UUID4): Estate the user belongs to.
        household_id (UUID4 | None): Optional household ID.
        status (bool): User activation status.
        created_at (datetime): User creation timestamp.
    """

    id: UUID4 = Field(..., description="Registered user ID")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    home_address: str = Field(..., description="User's home address")
    email: EmailStr = Field(..., description="User's email address")
    gender: Gender = Field(..., description="User's gender")
    role: Role = Field(..., description="Assigned user role")
    estate_id: Optional[UUID4] | None = Field(
        None, description="Estate the user belongs to"
    )
    household_id: Optional[UUID4] = Field(
        None, description="Optional household ID"
    )
    status: bool = Field(..., description="User activation status")
    created_at: datetime = Field(..., description="User creation timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4 | None) -> str | None:
        return str(estate_id) if estate_id else None

    @field_serializer("household_id")
    def serialize_household_id(
        self, household_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(household_id) if household_id else None

    model_config = model_config


class UpdateUserRequest(BaseModel):
    """
    Request model to update user information.
    All fields are optional - only provided fields will be updated.

    Attributes:
        first_name (str): User's first name.
        last_name (str): User's last name.
        home_address (str): User's home address.
        phone_number (str): User's phone number.
        gender (Gender): User's gender.
        role (Role): User's role.
        household_id (UUID4): Household ID.
    """

    first_name: Optional[str] = Field(
        None, description="User's first name", min_length=1
    )
    last_name: Optional[str] = Field(
        None, description="User's last name", min_length=1
    )
    home_address: Optional[str] = Field(
        None, description="User's home address", min_length=1
    )
    phone_number: Optional[str] = Field(
        None, description="User's phone number"
    )
    gender: Optional[Gender] = Field(None, description="User's gender")
    role: Optional[Role] = Field(None, description="User's role")
    household_id: Optional[UUID4] = Field(None, description="Household ID")

    @field_serializer("household_id")
    def serialize_household_id(
        self, household_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(household_id) if household_id else None

    model_config = model_config


class UpdateUserResponse(BaseModel):
    """
    Response model for user update operations.

    Attributes:
        id (UUID4): User ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID4 = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class GetUserResponse(BaseModel):
    """
    Response model to get a user by ID.

    Attributes:
        id (UUID4): User ID.
        first_name (str): User's first name.
        last_name (str): User's last name.
        email (EmailStr): User's email address.
        home_address (str): User's home address.
        phone_number (str): User's phone number.
        gender (Gender): User's gender.
        role (UserRole): User's role.
        estate_id (UUID4): Estate ID.
        household_id (UUID4): Household ID.
        status (bool): Account activation status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        is_deleted (bool): Deletion status.
    """

    id: UUID4 = Field(..., description="User ID")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    home_address: str = Field(..., description="User's home address")
    phone_number: Optional[str] = Field(
        None, description="User's phone number"
    )
    gender: Gender = Field(..., description="User's gender")
    role: Role = Field(..., description="User's role")
    estate_id: Optional[UUID4] = Field(None, description="Estate ID")
    household_id: Optional[UUID4] = Field(None, description="Household ID")
    status: bool = Field(..., description="Account activation status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(
        None, description="Last update timestamp"
    )
    is_deleted: bool = Field(False, description="Deletion status")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: Optional[UUID4]) -> str:
        return str(estate_id) if estate_id else None

    @field_serializer("household_id")
    def serialize_household_id(self, household_id: Optional[UUID4]) -> str:
        return str(household_id) if household_id else None

    model_config = model_config


class DeleteUserResponse(BaseModel):
    """
    Response model for user deletion (soft delete).

    Attributes:
        is_deleted (bool): Whether the user was deleted (soft delete).
        deleted_at (datetime): UTC Time when the user was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config


class SearchUserRequest(BaseModel):
    """
    Request model to search users with optional filters and pagination.

    Attributes:
        first_name (str): Filter by first name (partial match).
        last_name (str): Filter by last name (partial match).
        email (str): Filter by email (partial match).
        gender (Gender): Filter by user gender.
        role (Role): Filter by user role.
        estate_id (UUID4): Filter by estate ID.
        household_id (UUID4): Filter by household ID.
        status (bool): Filter by activation status.
        from_date (datetime): Filter by creation date (from).
        to_date (datetime): Filter by creation date (to).
        page (int): Page number for pagination.
        limit (int): Number of items per page.
    """

    first_name: Optional[str] = Field(None, description="Filter by first name")
    last_name: Optional[str] = Field(None, description="Filter by last name")
    email: Optional[str] = Field(None, description="Filter by email")
    gender: Optional[Gender] = Field(None, description="Filter by user gender")
    role: Optional[Role] = Field(None, description="Filter by role")
    estate_id: Optional[UUID4] = Field(None, description="Filter by estate ID")
    household_id: Optional[UUID4] = Field(
        None, description="Filter by household ID"
    )
    status: Optional[bool] = Field(
        None, description="Filter by activation status"
    )
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

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: Optional[UUID4]) -> Optional[str]:
        return str(estate_id) if estate_id else None

    @field_serializer("household_id")
    def serialize_household_id(
        self, household_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(household_id) if household_id else None

    model_config = model_config


class ListUserResponse(BaseModel):
    """
    Response model for user list/search operations.

    Attributes:
        total (int): Total number of users matching search criteria.
        page (int): Current page number.
        limit (int): Number of items per page.
        items (List[GetUserResponse]): List of user records.
    """

    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[GetUserResponse] = Field(..., description="List of users")

    model_config = model_config


class UserProfileRequest(BaseModel):
    """
    Request model for user profile.

    Attributes:

        user_id (UUID4): User ID.
    """

    user_id: UUID4 = Field(..., description="User ID")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    model_config = model_config


class UserProfileResponse(BaseModel):
    """
    User profile model.

    Attributes:

        user_id (UUID): User ID.
        first_name (str): User's first name.
        last_name (str): User's last name.
        home_address (str): User's home address.
        email (EmailStr): User's email address.
        phone_number (str): User's phone number.
        gender (Gender): User's gender.
        role (Role): User's role.
        estate_id (UUID4): Estate ID.
        estate_name (str): Estate name.
        household_primary_resident (str): Primary resident's name.
        status (bool): User's status.
    """

    user_id: UUID4 = Field(..., description="User ID")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    home_address: str = Field(..., description="User's home address")
    email: EmailStr = Field(..., description="User's email address")
    phone_number: str = Field(..., description="User's phone number")
    gender: Gender = Field(..., description="User's gender")
    role: Role = Field(..., description="User's role")
    estate_id: UUID4 = Field(..., description="Estate ID")
    estate_name: str = Field(..., description="Estate name")
    household_primary_resident: str | None = Field(
        ..., description="Primary resident's name"
    )
    status: bool = Field(..., description="User's status")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4) -> str:
        return str(estate_id)

    model_config = model_config


class SetPasswordRequest(BaseModel):
    """
    Request model for setting a new password.

    Attributes:

        user_id (UUID4): User ID.
        new_password (str): New password.
    """

    user_id: UUID4 = Field(..., description="User ID")
    new_password: str = Field(..., min_length=8, description="New password")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    model_config = model_config


class SetPasswordResponse(BaseModel):
    """
    Response model for setting a new password.

    Attributes:

        success (bool): Success status.
        message (str): Response message.
    """

    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")

    model_config = model_config


class UpdatePasswordRequest(BaseModel):
    """
    Request model for updating a user's password.

    Attributes:
        user_id (UUID4): User ID.
        current_password (str): Current password.
        new_password (str): New password.
    """

    user_id: UUID4 = Field(..., description="User ID")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    model_config = model_config
