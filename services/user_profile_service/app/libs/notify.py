import logging
from typing import Any, Dict

import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_NOTIFY_URL_SUFFIX = "api/v1/internal/notify"
_TOKEN_DEACTIVATE_BY_SESSION_SUFFIX = (
    "api/v1/internal/device-tokens/deactivate-by-session"
)
_TOKEN_BY_SESSION_SUFFIX = "api/v1/internal/device-tokens/by-session"
_TOKEN_BY_USER_SUFFIX = "api/v1/internal/device-tokens/by-user"


async def fire_notify(payload: Dict[str, Any]) -> None:
    """Best-effort fire-and-forget POST to the notification service.

    Silently ignores all errors so callers are never blocked.
    """
    url = settings.NOTIFICATION_SERVICE_URL
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{url}{_NOTIFY_URL_SUFFIX}",
                json=payload,
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except Exception:
        logger.exception("fire_notify failed — notification not delivered")


async def fire_deactivate_device_token_by_session(session_id: str) -> None:
    """Best-effort PATCH to soft-deactivate device tokens for a session (on logout)."""
    url = settings.NOTIFICATION_SERVICE_URL
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(
                f"{url}{_TOKEN_DEACTIVATE_BY_SESSION_SUFFIX}/{session_id}",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except Exception:
        logger.exception(
            "fire_deactivate_device_token_by_session failed for %s", session_id
        )


async def fire_remove_device_token_by_session(session_id: str) -> None:
    """Best-effort DELETE of all device tokens for a session (on explicit revoke)."""
    url = settings.NOTIFICATION_SERVICE_URL
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(
                f"{url}{_TOKEN_BY_SESSION_SUFFIX}/{session_id}",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except Exception:
        logger.exception(
            "fire_remove_device_token_by_session failed for %s", session_id
        )


async def fire_remove_device_token_by_user(user_id: str) -> None:
    """Best-effort DELETE of all device tokens for a user."""
    url = settings.NOTIFICATION_SERVICE_URL
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(
                f"{url}{_TOKEN_BY_USER_SUFFIX}/{user_id}",
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except Exception:
        logger.exception(
            "fire_remove_device_token_by_user failed for %s", user_id
        )


async def fire_notify_critical(payload: Dict[str, Any]) -> None:
    """POST to the notification service and raise HTTP 502 on any failure.

    Use for flows where a missing notification is unacceptable
    (e.g. forgot-password reset link).
    """
    url = settings.NOTIFICATION_SERVICE_URL
    if not url:
        raise HTTPException(
            status_code=502,
            detail="Notification service is not configured.",
        )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{url}{_NOTIFY_URL_SUFFIX}",
                json=payload,
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "fire_notify_critical HTTP %s: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(
            status_code=502,
            detail="Notification service returned an error.",
        ) from exc
    except Exception as exc:
        logger.exception("fire_notify_critical request failed")
        raise HTTPException(
            status_code=502,
            detail="Could not reach the notification service.",
        ) from exc
