from datetime import datetime, timezone

import jwt
from fastapi import BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from gatepass_auth.config import settings
from gatepass_auth.session_repo import update_last_active, validate_session

security = HTTPBearer()


async def _update_session_last_active(session_id: str) -> None:
    """Background task: refresh last_active_at for the current session."""
    await update_last_active(
        session_id,
        datetime.now(timezone.utc).isoformat(),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    Decode the JWT access token, validate the embedded session via a single
    JOIN query to db-service, and queue a last_active_at update in the
    background.

    Raises:
        HTTPException 403: If token scope is tos_pending or 2fa_pending.
        HTTPException 401: If token is missing, invalid, expired, session
            revoked, or session expired.

    Returns:
        dict: {id, role, email, estate_id, session_id}
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

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

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )

        session_id = payload.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No session associated with this token.",
            )

        data = await validate_session(session_id)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked.",
            )

        expires_at_str = data.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has expired.",
                )

        if background_tasks is not None:
            background_tasks.add_task(_update_session_last_active, session_id)

        return {
            "id": user_id,
            "role": payload.get("role"),
            "email": payload.get("email"),
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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
