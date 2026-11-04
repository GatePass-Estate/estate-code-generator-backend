from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from fastapi import Depends, Request
from user_agents import parse as parse_ua

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.session import SessionRepository
from app.repositories.totp_recovery_codes import TotpRecoveryCodesRepository
from app.repositories.user import UserRepository
from app.services.user import UserService

_MAX_DEVICE_NAME_LEN = 100


def _clean_device_name(value: str) -> str:
    value = unquote(value).strip()
    value = "".join(ch for ch in value if ch.isprintable())
    return value[:_MAX_DEVICE_NAME_LEN]


def _name_from_user_agent(ua: str) -> str:
    if "CFNetwork" in ua and "Darwin" in ua:
        return "iOS device"
    if "okhttp" in ua.lower():
        return "Android device"

    parsed = parse_ua(ua)
    browser = parsed.browser.family
    os = parsed.os.family

    if browser != "Other" and os != "Other":
        return f"{browser} on {os}"
    if os != "Other":
        return os
    return _clean_device_name(ua)


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def get_device_name(request: Request) -> str:
    header_name = request.headers.get("X-Device-Name")
    if header_name:
        cleaned = _clean_device_name(header_name)
        if cleaned:
            return cleaned

    ua = request.headers.get("User-Agent")
    if ua:
        return _name_from_user_agent(ua)

    return "Unknown device"


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
