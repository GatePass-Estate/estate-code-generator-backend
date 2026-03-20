from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import Optional
from app.schemas.user import (
    RegisterUserRequest,
    RegisterUserResponse,
    UpdateUserRequest,
    UpdateUserResponse,
    GetUserResponse,
    DeleteUserResponse,
    SearchUserRequest,
    ListUserResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    UpdatePasswordRequest,
    UserProfileRequest,
    UserProfileResponse,
    Role,
)
from app.schemas.guest import (
    RegisterGuestRequest,
    RegisterGuestResponse,
    UpdateGuestRequest,
    UpdateGuestResponse,
    ListGuestResponse,
    SearchGuestRequest,
    GetGuestResponse,
    DeleteGuestResponse,
)
from app.schemas.household import (
    UpdateHouseholdRequest,
    UpdateHouseholdResponse,
)
from app.schemas.email import (
    EmailTokenResponse,
)
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.libs.role_permissions import check_permission
from app.repositories.user import UserRepository
from app.repositories.guest import GuestRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.services.user import UserService
from app.services.guest import GuestService
from app.services.auth import get_current_user
from app.services.email import send_verification_email, send_welcome_email

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
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    # Only the root user can register a primary admin role
    if requester_role != Role.ROOT:
        if request.role == Role.PRIMARY_ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Only the root user can register a primary admin role.",
            )
        user_id = current_user["id"]
        estate_id = await service.get_estate_id_by_user_id(user_id)
        if estate_id != str(request.estate_id):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to register users for this estate.",
            )

    user, token = await service.register_user(request)

    # Trigger background email
    background_tasks.add_task(
        send_verification_email, user.email, user.first_name, token
    )

    # Return response model
    return user


@router.get("/profile/me", response_model=UserProfileResponse)
async def get_my_profile(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Get current user's profile."""
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )

    user_id = current_user["id"]
    request = UserProfileRequest(user_id=user_id)
    return await service.get_user_profile(request)


@router.get("/profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if requester_role != "security" and not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view users."
        )
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    same_estate = await service.check_same_estate(user_id, current_user["id"])
    if not same_estate:
        raise HTTPException(
            status_code=403, detail="You are not authorized to view this user."
        )
    payload = UserProfileRequest(user_id=user_id)
    return await service.get_user_profile(payload)


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

    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )

    # Parse datetime strings if provided
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from datetime import datetime

            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            from datetime import datetime

            to_date_obj = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid to_date format. Use ISO format.",
            )

    # For non-root users, restrict to users in their estate
    if requester_role != "root":
        # Get requester's user data to find their estate
        requester_user = await service.get_user(current_user["id"])
        estate_id = str(requester_user.estate_id)

    request = SearchUserRequest(
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

    return await service.search_users(request)


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
    current_user: dict = Depends(get_current_user),
):
    requester_role = current_user["role"]
    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view users"
        )
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    status = status or "true"

    if status not in {"true", "false", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")

    # Parse datetime strings if provided
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from datetime import datetime

            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            from datetime import datetime

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
    else:
        user_id = current_user["id"]
        estate_id = await service.get_estate_id_by_user_id(user_id)
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
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    return await service.verify_email(token)


@router.get("/verify/password-reset", response_model=EmailTokenResponse)
async def verify_password_reset_token(
    token: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """Validates a password reset token and returns the user_id to proceed."""
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    return await service.verify_password_reset_token(token)


@router.post("/password/reset", response_model=SetPasswordResponse)
async def reset_password(
    payload: SetPasswordRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """Resets the password for an active account
    (no current password required)."""
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    return await service.reset_password(payload)


@router.post("/validate/account", response_model=SetPasswordResponse)
async def set_password(
    payload: SetPasswordRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    user = await service.get_user(str(payload.user_id))
    result = await service.set_password_and_activate(payload)
    background_tasks.add_task(send_welcome_email, user.email, user.first_name)
    return result


@router.post("/password/update", response_model=SetPasswordResponse)
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
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    return await service.update_password(payload)


@router.post("/household/update", response_model=UpdateHouseholdResponse)
async def update_household(
    payload: UpdateHouseholdRequest,
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
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    return await service.update_user_household(payload)


@router.post("/guest/register", response_model=RegisterGuestResponse)
async def register_guest(
    request: RegisterGuestRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    repository = GuestRepository(ahttp_client)
    service = GuestService(repository)
    user_id = current_user["id"]

    request.resident_id = user_id
    return await service.register_guest(request)


@router.get("/guest/{guest_id}", response_model=GetGuestResponse)
async def get_guest(
    guest_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Get guest details by ID."""

    repository = GuestRepository(ahttp_client)
    service = GuestService(repository)
    user_id = current_user["id"]

    return await service.get_guest(guest_id, user_id)


@router.patch("/guest/{guest_id}", response_model=UpdateGuestResponse)
async def update_guest(
    guest_id: str,
    request: UpdateGuestRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Update an existing guest."""
    requester_id = current_user["id"]

    repository = GuestRepository(ahttp_client)
    service = GuestService(repository)
    return await service.update_guest(guest_id, requester_id, request)


@router.delete("/guest/{guest_id}", response_model=DeleteGuestResponse)
async def delete_guest(
    guest_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Soft delete a guest."""

    requester_id = current_user["id"]

    repository = GuestRepository(ahttp_client)
    service = GuestService(repository)
    return await service.delete_guest(guest_id, requester_id)


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
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Search and list guests with optional filters and pagination."""

    repository = GuestRepository(ahttp_client)
    service = GuestService(repository)
    user_id = current_user["id"]

    # Parse datetime strings if provided
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from datetime import datetime

            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            from datetime import datetime

            to_date_obj = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid to_date format. Use ISO format.",
            )

    request = SearchGuestRequest(
        guest_name=guest_name,
        guest_phone_number=guest_phone_number,
        guest_gender=guest_gender,
        relationship=relationship,
        from_date=from_date_obj,
        to_date=to_date_obj,
        page=page,
        limit=limit,
    )

    return await service.search_guests(request, user_id)


@router.post(
    "/{user_id}/resend-verification", response_model=SetPasswordResponse
)
async def resend_verification_email(
    user_id: str,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Regenerate and resend the email verification link
    for an unverified user."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to perform this action.",
        )

    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )

    if requester_role != "root":
        same_estate = await service.check_same_estate(
            user_id, current_user["id"]
        )
        if not same_estate:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to perform this action.",
            )

    email, first_name, token = await service.regenerate_verification_token(
        user_id
    )
    background_tasks.add_task(
        send_verification_email, email, first_name, token
    )

    return SetPasswordResponse(
        success=True,
        message="Verification email has been resent.",
    )


@router.get("/{user_id}", response_model=GetUserResponse)
async def get_user(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Get user details by ID."""
    requester_role = current_user["role"]

    # Restricted to Root users
    if requester_role != "root":
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view this user.",
        )

    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    return await service.get_user(user_id)


@router.patch("/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
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

    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    if requester_role != "root":
        same_estate = await service.check_same_estate(
            user_id, current_user["id"]
        )
        if not same_estate:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view this user.",
            )
    return await service.update_user(user_id, request)


@router.delete("/{user_id}", response_model=DeleteUserResponse)
async def delete_user(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
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

    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )
    if requester_role != "root":
        same_estate = await service.check_same_estate(
            user_id, current_user["id"]
        )
        if not same_estate:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view this user.",
            )
    return await service.delete_user(user_id)


@router.patch("/{user_id}/phone", response_model=UpdateUserResponse)
async def update_user_phone(
    user_id: str,
    phone_number: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Allow a user to update their own phone number."""
    # Only allow the user themself to update their phone number
    if str(current_user["id"]) != str(user_id):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to update this user's phone number",
        )

    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number is required")

    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )

    return await service.update_user_phone(user_id, phone_number)
