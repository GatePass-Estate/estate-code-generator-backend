from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify, fire_notify_critical
from app.libs.role_permissions import check_permission
from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.guest import GuestRepository
from app.repositories.household import HouseholdRepository
from app.repositories.schedule import (
    SCHEDULED_USER_CLOSURES_KEY,
    ScheduleRepository as ScheduleRepo,
)
from app.repositories.user import UserRepository
from app.schemas.email import EmailTokenResponse
from app.schemas.guest import (
    DeleteGuestResponse,
    GetGuestResponse,
    ListGuestResponse,
    RegisterGuestRequest,
    RegisterGuestResponse,
    SearchGuestRequest,
    UpdateGuestRequest,
    UpdateGuestResponse,
)
from app.schemas.user import (
    AdminCloseRequest,
    DeleteUserResponse,
    GetUserResponse,
    ListUserResponse,
    RegisterUserRequest,
    RegisterUserResponse,
    Role,
    SearchUserRequest,
    SetPasswordRequest,
    SetPasswordResponse,
    UpdatePasswordRequest,
    UpdateUserRequest,
    UpdateUserResponse,
    UserProfileRequest,
    UserProfileResponse,
)
from app.services.auth import get_current_user, get_current_user_unverified
from app.services.guest import GuestService
from app.services.user import UserService

router = APIRouter()


def get_user_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> UserService:
    return UserService(
        UserRepository(ahttp_client),
        EstateRepository(ahttp_client),
        HouseholdRepository(ahttp_client),
        AdminRepository(ahttp_client),
    )


def get_guest_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> GuestService:
    return GuestService(GuestRepository(ahttp_client))


def get_schedule_repo(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> ScheduleRepo:
    return ScheduleRepo(ahttp_client)


@router.post("/register", response_model=RegisterUserResponse)
async def register_user(
    request: RegisterUserRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to register users."
        )

    if requester_role != Role.ROOT:
        if request.role == Role.PRIMARY_ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Only the root user can register a primary admin role.",
            )
        estate_id = await service.get_estate_id_by_user_id(current_user["id"])
        if estate_id != str(request.estate_id):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to register users for this estate.",
            )

    user, token = await service.register_user(request)
    verification_url = (
        f"{settings.FRONTEND_BASE_URL}/activate?{urlencode({'token': token})}"
    )
    background_tasks.add_task(
        fire_notify,
        {
            "type": "EMAIL_VERIFICATION",
            "title": "Verify your email address",
            "body": "Please verify your email address"
            "to activate your account.",
            "recipient_user_ids": [str(user.id)],
            "metadata": {"verification_url": verification_url},
        },
    )
    return user


@router.delete("/me/account", response_model=DeleteUserResponse)
async def close_account(
    background_tasks: BackgroundTasks,
    service: UserService = Depends(get_user_service),
    schedule_repo: ScheduleRepo = Depends(get_schedule_repo),
    current_user: dict = Depends(get_current_user),
):
    """Close the authenticated user's own account."""
    user_id = current_user["id"]

    # Capture estate_id before deletion for admin notifications
    estate_id: str | None = None
    try:
        estate_id = await service.get_estate_id_by_user_id(user_id)
    except Exception:
        pass

    result = await service.close_account(user_id)

    # Clean up any pending scheduled closure for this user
    background_tasks.add_task(
        schedule_repo.remove_by_field,
        SCHEDULED_USER_CLOSURES_KEY,
        "user_id",
        user_id,
    )

    background_tasks.add_task(
        fire_notify_critical,
        {
            "type": "ACCOUNT_CLOSED",
            "title": "Your account has been closed",
            "body": "Your GatePass account has been closed.",
            "recipient_user_ids": [user_id],
        },
    )

    if estate_id:
        background_tasks.add_task(
            fire_notify,
            {
                "type": "ACCOUNT_CLOSED",
                "title": "Account closed",
                "body": ("A user in your estate has closed their account."),
                "fan_out": {
                    "estate_id": estate_id,
                    "roles": ["admin", "primary_admin"],
                },
            },
        )

    return result


@router.get("/profile/me", response_model=UserProfileResponse)
async def get_my_profile(
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user_unverified),
):
    """Get current user's profile."""
    return await service.get_user_profile(
        UserProfileRequest(user_id=current_user["id"])
    )


@router.get("/profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if requester_role != "security" and not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view users."
        )
    if not await service.check_same_estate(user_id, current_user["id"]):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view this user.",
        )
    return await service.get_user_profile(UserProfileRequest(user_id=user_id))


@router.get("/", response_model=ListUserResponse)
async def list_users(
    first_name: Optional[str] = Query(
        None, description="Filter by first name (partial match)"
    ),
    last_name: Optional[str] = Query(
        None, description="Filter by last name (partial match)"
    ),
    email: Optional[str] = Query(
        None, description="Filter by email (partial match)"
    ),
    role: Optional[Role] = Query(None, description="Filter by user role"),
    estate_id: Optional[str] = Query(
        None, description="Filter by estate ID (root only)"
    ),
    household_id: Optional[str] = Query(
        None, description="Filter by household ID"
    ),
    status: Optional[bool] = Query(
        None, description="Filter by activation status"
    ),
    from_date: Optional[str] = Query(
        None, description="Filter by creation date (from) - ISO format"
    ),
    to_date: Optional[str] = Query(
        None, description="Filter by creation date (to) - ISO format"
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Search and list users with optional filters and pagination."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view users."
        )

    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            to_date_obj = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid to_date format. Use ISO format.",
            )

    if requester_role != "root":
        requester_user = await service.get_user(current_user["id"])
        estate_id = str(requester_user.estate_id)

    return await service.search_users(
        SearchUserRequest(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=role,
            estate_id=estate_id,
            household_id=household_id,
            status=status,
            from_date=from_date_obj,
            to_date=to_date_obj,
            page=page,
            limit=limit,
        )
    )


@router.get("/all", response_model=ListUserResponse)
async def get_all_estate_users(
    status: Optional[str] = Query(
        None, description="Filter by user status: true, false, all"
    ),
    estate_id: Optional[str] = Query(
        None, description="Restrict to a specific estate (root only)"
    ),
    from_date: Optional[str] = Query(
        None, description="Filter by creation date (from) - ISO format"
    ),
    to_date: Optional[str] = Query(
        None, description="Filter by creation date (to) - ISO format"
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view users"
        )

    status = status or "true"
    if status not in {"true", "false", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            to_date_obj = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid to_date format. Use ISO format.",
            )

    if requester_role == "root":
        return await service.get_users_by_estate(
            estate_id=estate_id or None,
            status=status,
            page=page,
            limit=limit,
            from_date=from_date_obj,
            to_date=to_date_obj,
        )

    estate_id = await service.get_estate_id_by_user_id(current_user["id"])
    return await service.get_users_by_estate(
        estate_id,
        status=status,
        page=page,
        limit=limit,
        from_date=from_date_obj,
        to_date=to_date_obj,
    )


@router.get("/verify/email", response_model=EmailTokenResponse)
async def verify_email(
    token: str,
    service: UserService = Depends(get_user_service),
):
    return await service.verify_email(token)


@router.get("/verify/password-reset", response_model=EmailTokenResponse)
async def verify_password_reset_token(
    token: str,
    service: UserService = Depends(get_user_service),
):
    """Validates a password reset token and returns the user_id to proceed."""
    return await service.verify_password_reset_token(token)


@router.post("/password/reset", response_model=SetPasswordResponse)
async def reset_password(
    payload: SetPasswordRequest,
    background_tasks: BackgroundTasks,
    service: UserService = Depends(get_user_service),
):
    """Resets the password for an active account
    (no current password required)."""
    result = await service.reset_password(payload)
    background_tasks.add_task(
        fire_notify,
        {
            "type": "PASSWORD_RESET_CONFIRMED",
            "title": "Password reset successfully",
            "body": "Your GatePass password has been reset.",
            "recipient_user_ids": [str(payload.user_id)],
        },
    )
    background_tasks.add_task(
        fire_notify,
        {
            "type": "PASSWORD_CHANGED",
            "title": "Password changed",
            "body": "Your account password has been changed.",
            "recipient_user_ids": [str(payload.user_id)],
        },
    )
    return result


@router.post("/validate/account", response_model=SetPasswordResponse)
async def set_password(
    payload: SetPasswordRequest,
    background_tasks: BackgroundTasks,
    service: UserService = Depends(get_user_service),
):
    result = await service.set_password_and_activate(payload)
    background_tasks.add_task(
        fire_notify,
        {
            "type": "WELCOME",
            "title": "Welcome to GatePass",
            "body": "Your account has been activated. Welcome to GatePass!",
            "recipient_user_ids": [str(payload.user_id)],
        },
    )
    return result


@router.post("/password/update", response_model=SetPasswordResponse)
async def update_password(
    payload: UpdatePasswordRequest,
    background_tasks: BackgroundTasks,
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    if str(payload.user_id) != str(current_user["id"]):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to update this user's password.",
        )
    result = await service.update_password(payload)
    background_tasks.add_task(
        fire_notify,
        {
            "type": "PASSWORD_CHANGED",
            "title": "Password changed",
            "body": "Your account password has been changed.",
            "recipient_user_ids": [str(payload.user_id)],
        },
    )
    return result


@router.post("/guest/register", response_model=RegisterGuestResponse)
async def register_guest(
    request: RegisterGuestRequest,
    service: GuestService = Depends(get_guest_service),
    current_user: dict = Depends(get_current_user),
):
    request.resident_id = current_user["id"]
    return await service.register_guest(request)


@router.get("/guest/{guest_id}", response_model=GetGuestResponse)
async def get_guest(
    guest_id: str,
    service: GuestService = Depends(get_guest_service),
    current_user: dict = Depends(get_current_user),
):
    """Get guest details by ID."""
    return await service.get_guest(guest_id, current_user["id"])


@router.patch("/guest/{guest_id}", response_model=UpdateGuestResponse)
async def update_guest(
    guest_id: str,
    request: UpdateGuestRequest,
    service: GuestService = Depends(get_guest_service),
    current_user: dict = Depends(get_current_user),
):
    """Update an existing guest."""
    return await service.update_guest(guest_id, current_user["id"], request)


@router.delete("/guest/{guest_id}", response_model=DeleteGuestResponse)
async def delete_guest(
    guest_id: str,
    service: GuestService = Depends(get_guest_service),
    current_user: dict = Depends(get_current_user),
):
    """Soft delete a guest."""
    return await service.delete_guest(guest_id, current_user["id"])


@router.get("/guest", response_model=ListGuestResponse)
async def list_guests(
    guest_name: Optional[str] = Query(
        None, description="Filter by guests name (partial match)"
    ),
    guest_phone_number: Optional[str] = Query(
        None, description="Filter by Phone number (partial match)"
    ),
    guest_gender: Optional[str] = Query(
        None, description="Filter by Gender (partial match)"
    ),
    relationship: Optional[str] = Query(
        None, description="Filter by relationship with resident"
    ),
    from_date: Optional[str] = Query(
        None, description="Filter by creation date (from) - ISO format"
    ),
    to_date: Optional[str] = Query(
        None, description="Filter by creation date (to) - ISO format"
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    service: GuestService = Depends(get_guest_service),
    current_user: dict = Depends(get_current_user),
):
    """Search and list guests with optional filters and pagination."""
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            to_date_obj = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid to_date format. Use ISO format.",
            )

    return await service.search_guests(
        SearchGuestRequest(
            guest_name=guest_name,
            guest_phone_number=guest_phone_number,
            guest_gender=guest_gender,
            relationship=relationship,
            from_date=from_date_obj,
            to_date=to_date_obj,
            page=page,
            limit=limit,
        ),
        current_user["id"],
    )


@router.post(
    "/{user_id}/resend-verification", response_model=SetPasswordResponse
)
async def resend_verification_email(
    user_id: str,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Regenerate and resend the email verification
    link for an unverified user."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to perform this action.",
        )

    if requester_role != "root":
        if not await service.check_same_estate(user_id, current_user["id"]):
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to perform this action.",
            )

    regenerated_user_id, token = await service.regenerate_verification_token(
        user_id
    )
    verification_url = (
        f"{settings.FRONTEND_BASE_URL}/activate?{urlencode({'token': token})}"
    )
    background_tasks.add_task(
        fire_notify,
        {
            "type": "EMAIL_VERIFICATION",
            "title": "Verify your email address",
            "body": "Please verify your email address"
            "to activate your account.",
            "recipient_user_ids": [regenerated_user_id],
            "metadata": {"verification_url": verification_url},
        },
    )
    return SetPasswordResponse(
        success=True,
        message="Verification email has been resent.",
    )


@router.post("/{user_id}/close")
async def close_user_account(
    user_id: str,
    request: AdminCloseRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    schedule_repo: ScheduleRepo = Depends(get_schedule_repo),
    current_user: dict = Depends(get_current_user),
):
    """
    Admin-initiated account closure.

    - `close_at` omitted or null → immediate permanent closure.
    - `close_at` is a future datetime → scheduled closure via Redis.
      Cannot exceed SCHEDULE_CLOSE_MAX_DAYS days from now.
    """
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_deactivate_user"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to close user accounts.",
        )

    # Capture estate_id before deletion for admin notifications
    estate_id: str | None = None
    try:
        estate_id = await service.get_estate_id_by_user_id(user_id)
    except Exception:
        pass

    if request.close_at is None:
        # Immediate closure — also remove any pending scheduled entry
        result = await service.admin_close_account(
            user_id=user_id,
            actor_user_id=current_user["id"],
            actor_role=requester_role,
        )
        background_tasks.add_task(
            schedule_repo.remove_by_field,
            SCHEDULED_USER_CLOSURES_KEY,
            "user_id",
            user_id,
        )
        background_tasks.add_task(
            fire_notify_critical,
            {
                "type": "ACCOUNT_DEACTIVATED",
                "title": "Your account has been closed",
                "body": (
                    "Your GatePass account has been closed"
                    " by an administrator."
                ),
                "recipient_user_ids": [user_id],
            },
        )
        if estate_id:
            background_tasks.add_task(
                fire_notify,
                {
                    "type": "ACCOUNT_DEACTIVATED",
                    "title": "Account closed",
                    "body": (
                        "An account in your estate has been closed"
                        " by an administrator."
                    ),
                    "fan_out": {
                        "estate_id": estate_id,
                        "roles": ["admin", "primary_admin"],
                    },
                },
            )
        return result

    # Scheduled closure
    result = await service.schedule_close_account(
        user_id=user_id,
        actor_user_id=current_user["id"],
        actor_role=requester_role,
        close_at=request.close_at,
        schedule_repo=schedule_repo,
    )
    background_tasks.add_task(
        fire_notify,
        {
            "type": "ACCOUNT_DEACTIVATION_SCHEDULED",
            "title": "Account closure scheduled",
            "body": (
                "Your GatePass account is scheduled to be closed on "
                f"{result['close_at'].strftime('%Y-%m-%d')}."
            ),
            "recipient_user_ids": [user_id],
            "metadata": {"close_at": result["close_at"].isoformat()},
        },
    )
    return {"success": True, "message": "Account closure scheduled."}


@router.delete("/{user_id}/close")
async def cancel_scheduled_close(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    schedule_repo: ScheduleRepo = Depends(get_schedule_repo),
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a pending scheduled account closure.
    Returns 404 if no scheduled closure exists for this user.
    """
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_deactivate_user"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to cancel account closures.",
        )

    await service.cancel_scheduled_close(user_id, schedule_repo)
    return {"success": True, "message": "Scheduled closure cancelled."}


@router.get("/{user_id}", response_model=GetUserResponse)
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Get user details by ID."""
    if current_user["role"] != "root":
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view this user.",
        )
    return await service.get_user(user_id)


@router.patch("/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Update an existing user."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to update this user.",
        )

    if requester_role != "root":
        if not await service.check_same_estate(user_id, current_user["id"]):
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view this user.",
            )
    return await service.update_user(user_id, request)


@router.delete("/{user_id}", response_model=DeleteUserResponse)
async def delete_user(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Soft delete a user."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to delete users."
        )

    if requester_role != "root":
        if not await service.check_same_estate(user_id, current_user["id"]):
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view this user.",
            )
    return await service.delete_user(user_id)


@router.patch("/{user_id}/phone", response_model=UpdateUserResponse)
async def update_user_phone(
    user_id: str,
    phone_number: str,
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Allow a user to update their own phone number."""
    if str(current_user["id"]) != str(user_id):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to update this user's phone number",
        )
    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number is required")
    return await service.update_user_phone(user_id, phone_number)
