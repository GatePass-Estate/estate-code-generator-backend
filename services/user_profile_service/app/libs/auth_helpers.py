from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.session import SessionRepository
from app.repositories.totp_recovery_codes import TotpRecoveryCodesRepository
from app.repositories.user import UserRepository
from app.services.user import UserService


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def get_device_name(request: Request) -> str | None:
    return request.headers.get("User-Agent")


def session_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        days=settings.SESSION_EXPIRE_DAYS
    )


def make_user_service(ahttp_client: AsyncHttpHandler) -> UserService:
    return UserService(
        UserRepository(ahttp_client),
        EstateRepository(ahttp_client),
        HouseholdRepository(ahttp_client),
        AdminRepository(ahttp_client),
    )


# --- Depends() providers ---


def get_user_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> UserService:
    return make_user_service(ahttp_client)


def get_session_repo(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> SessionRepository:
    return SessionRepository(ahttp_client)


def get_totp_recovery_repo(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> TotpRecoveryCodesRepository:
    return TotpRecoveryCodesRepository(ahttp_client)


def get_auth_service(
    user_service: UserService = Depends(get_user_service),
    session_repo: SessionRepository = Depends(get_session_repo),
    totp_recovery_repo: TotpRecoveryCodesRepository = Depends(
        get_totp_recovery_repo
    ),
):
    from app.services.auth import AuthService

    return AuthService(user_service, session_repo, totp_recovery_repo)
