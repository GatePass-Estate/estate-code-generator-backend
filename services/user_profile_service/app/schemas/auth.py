from datetime import datetime
from typing import List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, ConfigDict

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "ForgotPasswordRequest",
    "AcceptTosRequest",
    "TwoFAVerifyRequest",
    "TwoFARecoverRequest",
    "TwoFASetupResponse",
    "TwoFAEnableRequest",
    "TwoFAEnableResponse",
    "TwoFADisableRequest",
    "TwoFARegenerateCodesRequest",
    "TwoFARegenerateCodesResponse",
    "SessionResponse",
    "SessionListResponse",
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
        access_token (str): JWT access token (or tos_pending/2fa_pending token)
        token_type (str): Type of token. Always 'bearer'.
        requires_tos_acceptance (bool): If True, POST /auth/accept-tos required
        requires_2fa (bool): If True, POST /auth/2fa/verify required.
        two_fa_token (str): Short-lived 2FA-pending token
        (set when requires_2fa=True).
    """

    success: bool = Field(..., description="Login success status")
    role: Optional[Role] = Field(None, description="User's role")
    access_token: Optional[str] = Field(None, description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    requires_tos_acceptance: bool = Field(
        default=False,
        description="True if the user must accept the TOS before continuing",
    )
    requires_2fa: bool = Field(
        default=False,
        description="True if the user must complete 2FA verification",
    )
    two_fa_token: Optional[str] = Field(
        default=None,
        description="Short-lived 2FA-pending token (when requires_2fa=True)",
    )

    model_config = model_config


class TwoFAVerifyRequest(BaseModel):
    """Request to complete 2FA login with a TOTP code."""

    two_fa_token: str = Field(..., description="2FA-pending JWT from login")
    code: str = Field(..., description="6-digit TOTP code")

    model_config = model_config


class TwoFARecoverRequest(BaseModel):
    """Request to log in using a recovery code (disables 2FA)."""

    two_fa_token: str = Field(..., description="2FA-pending JWT from login")
    recovery_code: str = Field(..., description="One-time recovery code")

    model_config = model_config


class TwoFASetupResponse(BaseModel):
    """Response after initiating 2FA setup."""

    provisioning_uri: str = Field(
        ..., description="TOTP provisioning URI for QR code"
    )
    secret: str = Field(..., description="Base32 TOTP secret (shown once)")

    model_config = model_config


class TwoFAEnableRequest(BaseModel):
    """Request to confirm and enable 2FA."""

    code: str = Field(..., description="6-digit TOTP code to confirm setup")

    model_config = model_config


class TwoFAEnableResponse(BaseModel):
    """Response after enabling 2FA — recovery codes shown once."""

    recovery_codes: List[str] = Field(
        ..., description="One-time recovery codes"
    )

    model_config = model_config


class TwoFADisableRequest(BaseModel):
    """Request to disable 2FA (requires current TOTP code)."""

    code: str = Field(..., description="6-digit TOTP code")

    model_config = model_config


class TwoFARegenerateCodesRequest(BaseModel):
    """Request to regenerate recovery codes (requires current TOTP code)."""

    code: str = Field(..., description="6-digit TOTP code")

    model_config = model_config


class TwoFARegenerateCodesResponse(BaseModel):
    """New recovery codes after regeneration — shown once."""

    recovery_codes: List[str] = Field(
        ..., description="New one-time recovery codes"
    )

    model_config = model_config


class SessionResponse(BaseModel):
    """A single session record."""

    id: str = Field(..., description="Session ID")
    device_name: Optional[str] = Field(None, description="Device name")
    ip_address: Optional[str] = Field(None, description="IP address")
    last_active_at: datetime = Field(..., description="Last active time")
    expires_at: datetime = Field(..., description="Expiry time")
    is_2fa_verified: bool = Field(..., description="Whether 2FA was completed")
    created_at: datetime = Field(..., description="Session creation time")

    model_config = model_config


class SessionListResponse(BaseModel):
    """List of active sessions."""

    items: List[SessionResponse] = Field(..., description="Session records")
    total: int = Field(..., description="Total number of sessions")

    model_config = model_config
