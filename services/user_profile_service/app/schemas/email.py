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
