from enum import Enum
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    UUID4,
    ConfigDict,
    field_serializer,
)
from typing import Optional

__all__ = ["RegisterUserRequest", "RegisterUserResponse"]

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


class RegisterUserRequest(BaseModel):
    """
    Base request model to register a user.

    Attributes:
        first_name (str): User's first name.
        last_name (str): User's last name
        email (EmailStr): User's email address.
        role (Role): User role.
        estate_id (UUID4): Estate the user belongs to.
        household_id (UUID4): Optional household ID.
    """

    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
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
        email (EmailStr): User's email address.
        role (Role): Assigned user role.
        estate_id (UUID4): Estate the user belongs to.
        household_id (UUID4 | None): Optional household ID.
        status (bool): User activation status.
    """

    id: UUID4 = Field(..., description="Registered user ID")
    first_name: str = Field(..., description="User's first name")
    last_name: str = Field(..., description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    role: Role = Field(..., description="Assigned user role")
    estate_id: UUID4 = Field(..., description="Estate the user belongs to")
    household_id: Optional[UUID4] = Field(
        None, description="Optional household ID"
    )
    status: bool = Field(..., description="User activation status")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4) -> str:
        return str(estate_id)

    @field_serializer("household_id")
    def serialize_household_id(
        self, household_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(household_id) if household_id else None

    model_config = model_config


class EmailTokenRequest(BaseModel):
    """
    Request model for email token.

    Attributes:

        token (str): Email token.
    """

    token: str = Field(..., description="Email token")
    model_config = model_config


class EmailTokenResponse(BaseModel):
    """
    Response model for email token.

    Attributes:

        user_id (UUID4): User ID.
        email (EmailStr): User email.
        must_change_password (bool): Must change password.
    """

    user_id: UUID4 = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    must_change_password: bool = Field(..., description="Must change password")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    model_config = model_config


class SetPasswordRequest(BaseModel):
    """
    Request model for setting a new password.

    Attributes:

        user_id (UUID4): User ID.
        new_password (str): New password.
    """

    user_id: UUID4 = Field(..., description="User ID")
    new_password: str = Field(..., description="New password")

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
