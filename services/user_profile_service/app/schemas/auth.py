from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum
from typing import Optional
from uuid import UUID

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "ForgotPasswordRequest",
    "AcceptTosRequest",
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


class LoginRequest(BaseModel):
    """
    Base request model for user login.

    Attributes:
        email (EmailStr): User's email address.
        password (str): User's plaintext password.
        estate_id (UUID): Estate the user is logging into. None for root.
    """

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    estate_id: Optional[UUID] = Field(
        default=None, description="Estate ID to log into. Omit for root login."
    )

    model_config = model_config


class ForgotPasswordRequest(BaseModel):
    """
    Request model for initiating a password reset.

    Attributes:
        email (EmailStr): The email address of the account to reset.
        estate_id (UUID): The estate the account belongs to. None for root.
    """

    email: EmailStr = Field(..., description="Email address of the account")
    estate_id: Optional[UUID] = Field(
        default=None,
        description="Estate ID the account belongs to. Omit for root.",
    )

    model_config = model_config


class AcceptTosRequest(BaseModel):
    """
    Request model for accepting the Terms of Service.

    Attributes:
        tos_token (str): The TOS-pending JWT token received at login.
    """

    tos_token: str = Field(..., description="TOS-pending JWT token from login")

    model_config = model_config


class LoginResponse(BaseModel):
    """
    Response model returned after successful authentication.

    Attributes:
        success (bool): Indicates if the login was successful.
        role (Role): User's role.
        access_token (str): JWT access token (or tos_pending token if TOS
            acceptance is required).
        token_type (str): Type of token. Always 'bearer'.
        requires_tos_acceptance (bool): If True, the user must call
            POST /auth/accept-tos before accessing the app.
    """

    success: bool = Field(..., description="Login success status")
    role: Role = Field(..., description="User's role")
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    requires_tos_acceptance: bool = Field(
        default=False,
        description="True if the user must accept the TOS before continuing",
    )

    model_config = model_config
