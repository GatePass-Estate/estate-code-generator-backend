from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    UUID4,
    ConfigDict,
    field_serializer,
)

__all__ = [
    "EmailTokenRequest",
    "EmailTokenResponse",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


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

        valid (bool): Always True — invalid tokens raise HTTP 400, so a
            200 response with this field set guarantees the token was accepted.
        user_id (UUID4): User ID.
        email (EmailStr): User email.
        must_change_password (bool): True for email verification tokens
            (account setup), False for password reset tokens.
        message (str): Human-readable status message.
    """

    valid: bool = Field(True, description="Token is valid")
    user_id: UUID4 = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    must_change_password: bool = Field(..., description="Must change password")
    message: str = Field(..., description="Status message")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    model_config = model_config
