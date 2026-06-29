from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from gatepass_auth import get_current_user  # noqa: F401

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = settings.LOGIN_EXPIRE_MINUTES


def generate_access_token(user: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_user_details(
    http_client: AsyncHttpHandler,
    user_id: str,
) -> bool:
    """
    Retrieves user details using a given user_id.
    """
    url = f"{settings.DB_SERVICE_URL}api/v1/userprofile/users/{user_id}"
    return await http_client.async_get(url)
