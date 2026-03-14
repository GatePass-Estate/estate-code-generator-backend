from fastapi import APIRouter, Depends, BackgroundTasks
from app.schemas.auth import LoginRequest, LoginResponse, ForgotPasswordRequest
from app.schemas.user import SetPasswordResponse
from app.repositories.user import UserRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.services.auth import generate_access_token
from app.services.user import UserService
from app.services.email import send_password_reset_email
from app.libs.http_handler import get_http_handler, AsyncHttpHandler

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: LoginRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Authenticates a user using email and password, and returns a JWT token.
    """
    repo = UserRepository(ahttp_client)
    user = await repo.authenticate_user(request.email, request.password)
    token = generate_access_token(user)
    return LoginResponse(success=True, role=user["role"], access_token=token)


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
        email, token = result
        background_tasks.add_task(send_password_reset_email, email, token)

    return SetPasswordResponse(
        success=True,
        message=(
            "If an account with that email exists, "
            "a password reset link has been sent."
        ),
    )
