from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

security = HTTPBearer()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = settings.LOGIN_EXPIRE_MINUTES


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Extracts user info from JWT access token in Authorization header.

    Raises:
        HTTPException: If token is missing, invalid, or expired.

    Returns:
        dict: User details like { id, role, email, etc. }
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "id": payload["sub"],
            "role": payload["role"],
            "email": payload["email"],
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


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
