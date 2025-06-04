from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.schemas.register import (
    RegisterUserRequest,
    RegisterUserResponse,
    # EmailTokenRequest,
    EmailTokenResponse,
    SetPasswordRequest,
    SetPasswordResponse,
)
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.libs.role_permissions import check_permission
from app.repositories.user_repository import UserRepository
from app.services.user_profile_service import UserProfileService
from app.services.auth import get_current_user
from app.services.email import send_verification_email

router = APIRouter()


@router.post("/register", response_model=RegisterUserResponse)
async def register_user(
    request: RegisterUserRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    # 1. Extract role of the requester
    requester_role = current_user["role"]

    # 2. Check permission to register users
    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to register users."
        )

    # 3. Proceed with user creation
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    user, token = await service.register_user(request)

    # 4. Trigger background email
    background_tasks.add_task(send_verification_email, user.email, token)

    # 5. Return response model
    return user


@router.get("/verify-email", response_model=EmailTokenResponse)
async def verify_email(
    token: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    return await service.verify_email(token)


@router.post("/set-password", response_model=SetPasswordResponse)
async def set_password(
    payload: SetPasswordRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    return await service.set_user_password(payload)
