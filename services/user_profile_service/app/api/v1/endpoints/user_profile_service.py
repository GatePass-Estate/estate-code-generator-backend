from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Optional
from app.schemas.user_profile import (
    RegisterUserRequest,
    RegisterUserResponse,
    # EmailTokenRequest,
    EmailTokenResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    UpdatePasswordRequest,
    UserProfileRequest,
    UserProfileResponse,
    UpdateUserHouseholdRequest,
    UpdateUserHouseholdResponse,
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
    # Extract role of the requester
    requester_role = current_user["role"]

    # Check permission to register users
    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to register users."
        )

    # Proceed with user creation
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    user, token = await service.register_user(request)

    # Trigger background email
    background_tasks.add_task(send_verification_email, user.email, token)

    # Return response model
    return user


@router.get("/user-profile", response_model=UserProfileResponse)
async def get_profile(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    user_id = current_user["id"]
    payload = UserProfileRequest(user_id=user_id)
    return await service.get_user_profile(payload)


@router.get("/user-profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view users."
        )
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    payload = UserProfileRequest(user_id=user_id)
    return await service.get_user_profile(payload)


@router.get("/estate-users", response_model=list[RegisterUserResponse])
async def get_all_estate_users(
    status: Optional[str] = Query(
        None, description="Filter by user status: true, false, all"
    ),
    estate_id: Optional[str] = Query(
        None, description="Restrict to a specific estate (root only)"
    ),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized for this action"
        )
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    status = status or "true"

    if status not in {"true", "false", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    if requester_role == "root":
        return await service.get_all_users_in_estate(
            estate_id=estate_id or None, status=status
        )
    else:
        user_id = current_user["id"]
        estate_id = await service.get_estate_id_from_user_id(user_id)
        return await service.get_all_users_in_estate(estate_id, status=status)


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


@router.post("/update-password", response_model=SetPasswordResponse)
async def update_password(
    payload: UpdatePasswordRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    if str(payload.user_id) != str(current_user["id"]):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to update this user's password.",
        )
    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    return await service.update_user_password(payload)


@router.post("/update-household", response_model=UpdateUserHouseholdResponse)
async def update_household(
    payload: UpdateUserHouseholdRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if not await check_permission(
        ahttp_client, requester_role, "can_add_household_member"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to perform action."
        )

    repository = UserRepository(ahttp_client)
    service = UserProfileService(repository)
    return await service.update_user_household(payload)
