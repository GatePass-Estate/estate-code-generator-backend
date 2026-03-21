from fastapi import APIRouter, Depends, BackgroundTasks
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    ForgotPasswordRequest,
    AcceptTosRequest,
)
from app.schemas.user import SetPasswordResponse
from app.repositories.user import UserRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.services.auth import generate_access_token
from app.services.token import generate_tos_pending_token
from app.services.user import UserService
from app.services.email import send_password_reset_email
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.core.config import settings

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: LoginRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Authenticates a user using email and password, and returns a JWT token.

    If the user has not accepted the current TOS version, a restricted
    tos_pending token is returned with requires_tos_acceptance=True.
    The user must call POST /auth/accept-tos before accessing the app.
    """
    repo = UserRepository(ahttp_client)
    user = await repo.authenticate_user(request.email, request.password)

    if user.get("tos_accepted_version") != settings.TOS_VERSION:
        tos_token = generate_tos_pending_token(user["id"])
        return LoginResponse(
            success=True,
            role=user["role"],
            access_token=tos_token,
            requires_tos_acceptance=True,
        )

    token = generate_access_token(user)
    return LoginResponse(success=True, role=user["role"], access_token=token)


@router.post("/accept-tos", response_model=LoginResponse)
async def accept_tos(
    request: AcceptTosRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Accepts the current Terms of Service and returns a full access token.

    The tos_token must be the token received from POST /auth/login when
    requires_tos_acceptance is True.
    """
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )

    user = await service.accept_tos(request.tos_token)
    token = generate_access_token(user)
    return LoginResponse(
        success=True,
        role=user["role"],
        access_token=token,
        requires_tos_acceptance=False,
    )


@router.post("/forgot-password", response_model=SetPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> SetPasswordResponse:
    """
    Initiates the forgot password flow.

    Sends a password reset link to the provided email if an active account
    exists. Always returns success to prevent email enumeration.
    """
    repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = UserService(
        repository, estate_repository, household_repository, admin_repository
    )

    result = await service.forgot_password(request.email)
    if result:
        email, first_name, token = result
        background_tasks.add_task(
            send_password_reset_email, email, first_name, token
        )

    return SetPasswordResponse(
        success=True,
        message=(
            "If an account with that email exists, "
            "a password reset link has been sent."
        ),
    )
