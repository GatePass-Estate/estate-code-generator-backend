from datetime import datetime, timedelta, timezone

import jwt
from fastapi import BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.session import SessionRepository
from app.repositories.user import UserRepository

security = HTTPBearer()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = settings.LOGIN_EXPIRE_MINUTES


async def _update_session_last_active(
    session_repo: SessionRepository, session_id: str
) -> None:
    """Background task: refresh last_active_at for the current session."""
    await session_repo.update_session(
        session_id,
        {"last_active_at": datetime.now(timezone.utc).isoformat()},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    Extracts user info from JWT access token in Authorization header.
    Validates that the embedded session is still active (not expired /
    soft-deleted), then queues a last_active_at update as a background task.

    Raises:
        HTTPException: If token is missing, invalid, expired, or session is
            no longer valid.

    Returns:
        dict: User details {id, role, email, estate_id, session_id}
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        scope = payload.get("scope")
        if scope == "tos_pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please accept the Terms of Service to continue.",
            )
        if scope == "2fa_pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please complete 2FA verification to continue.",
            )

        user_id = payload["sub"]
        session_id = payload.get("session_id")

        user_repo = UserRepository(ahttp_client)
        valid_user = await user_repo.check_user_exists(user_id)
        if not valid_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Validate session
        if session_id:
            session_repo = SessionRepository(ahttp_client)
            session = await session_repo.get_session(session_id)
            if not session or session.get("is_deleted"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked.",
                )
            expires_at_str = session.get("expires_at")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session has expired.",
                    )
            # Update last_active_at in the background
            if background_tasks is not None:
                background_tasks.add_task(
                    _update_session_last_active, session_repo, session_id
                )

        return {
            "id": payload["sub"],
            "role": payload["role"],
            "email": payload["email"],
            "estate_id": payload.get("estate_id"),
            "session_id": session_id,
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


def generate_access_token(user: dict, session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "estate_id": user.get("estate_id"),
        "session_id": session_id,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
