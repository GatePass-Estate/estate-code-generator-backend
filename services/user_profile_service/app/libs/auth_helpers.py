from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
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
        minutes=settings.LOGIN_EXPIRE_MINUTES
    )


def make_user_service(ahttp_client: AsyncHttpHandler) -> UserService:
    return UserService(
        UserRepository(ahttp_client),
        EstateRepository(ahttp_client),
        HouseholdRepository(ahttp_client),
        AdminRepository(ahttp_client),
    )
