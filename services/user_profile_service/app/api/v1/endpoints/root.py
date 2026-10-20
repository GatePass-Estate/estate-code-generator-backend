from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from gatepass_auth import get_current_user
from gatepass_rbac import require_roles
from pydantic import BaseModel, Field

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.password_utils import hash_password
from app.repositories.user import UserRepository
from app.services.token import (
    generate_email_token,
    generate_password_reset_token,
)

router = APIRouter()


class ActivateUserRequest(BaseModel):
    user_id: UUID
    password: str = Field(..., min_length=8)


class GenerateTokenRequest(BaseModel):
    user_id: UUID
    token_type: str = Field(
        "email_verification",
        description="Token type: 'email_verification' or 'password_reset'",
    )


@router.post(
    "/activate-user",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description=(
        "Directly activate a user account and set their password. "
        "Bypasses the email-verification token flow. Root only."
    ),
)
async def activate_user(
    body: ActivateUserRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    require_roles(
        current_user["role"],
        ("root",),
        detail="Only root users can perform this operation.",
    )

    repo = UserRepository(ahttp_client)
    user = await repo.get_user_by_id(str(body.user_id))
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    if user.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already activated.",
        )

    hashed = hash_password(body.password)
    url = f"{repo.users_endpoint}/{body.user_id}"
    response = await repo.client.async_patch(
        url, json_data={"password": hashed, "status": True}
    )
    if not response:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user.",
        )
    return {
        "message": "User activated successfully.",
        "user_id": str(body.user_id),
    }


@router.post(
    "/generate-token",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description=(
        "Generate an email-verification or password-reset token for a user. "
        "Useful for testing flows that normally require email delivery. "
        "Root only."
    ),
)
async def generate_token(
    body: GenerateTokenRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    require_roles(
        current_user["role"],
        ("root",),
        detail="Only root users can perform this operation.",
    )

    repo = UserRepository(ahttp_client)
    user = await repo.get_user_by_id(str(body.user_id))
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if body.token_type == "email_verification":
        token = generate_email_token(body.user_id)
    elif body.token_type == "password_reset":
        if not user.status:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot generate reset token for an inactive account.",
            )
        token = generate_password_reset_token(body.user_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "token_type must be 'email_verification' "
                "or 'password_reset'."
            ),
        )

    return {
        "token": token,
        "token_type": body.token_type,
        "user_id": str(body.user_id),
    }
