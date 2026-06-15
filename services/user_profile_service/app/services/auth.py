from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.config import settings
from datetime import datetime, timedelta, timezone
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.repositories.user import UserRepository

security = HTTPBearer()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = settings.LOGIN_EXPIRE_MINUTES


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
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
        if payload.get("scope") == "tos_pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please accept the Terms of Service to continue.",
            )
        user_id = payload["sub"]
        user_repo = UserRepository(ahttp_client)
        valid_user = await user_repo.check_user_exists(user_id)
        if not valid_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return {
            "id": payload["sub"],
            "role": payload["role"],
            "email": payload["email"],
            "estate_id": payload.get("estate_id"),
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
        "estate_id": user.get("estate_id"),
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
