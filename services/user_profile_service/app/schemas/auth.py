from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum

__all__ = ["LoginRequest", "LoginResponse"]

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
    """

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

    model_config = model_config


class LoginResponse(BaseModel):
    """
    Response model returned after successful authentication.

    Attributes:
        success (bool): Indicates if the login was successful.
        role (Role): User's role.
        access_token (str): JWT access token.
        token_type (str): Type of token. Always 'bearer'.
    """

    success: bool = Field(..., description="Login success status")
    role: Role = Field(..., description="User's role")
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")

    model_config = model_config
