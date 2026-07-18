import logging
from typing import Any, Dict

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_NOTIFY_SUFFIX = "api/v1/internal/notify"
_FEEDBACK_SUFFIX = "api/v1/internal/feedback"
_DEACTIVATE_BY_SESSION_SUFFIX = (
    "api/v1/internal/device-tokens/deactivate-by-session"
)
_BY_SESSION_SUFFIX = "api/v1/internal/device-tokens/by-session"
_BY_USER_SUFFIX = "api/v1/internal/device-tokens/by-user"


async def fire_notify(
    payload: Dict[str, Any],
    notification_service_url: str,
    internal_api_key: str,
) -> None:
    """Best-effort fire-and-forget POST to the notification service.

    Silently ignores all errors so callers are never blocked.
    """
    if not notification_service_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{notification_service_url}{_NOTIFY_SUFFIX}",
                json=payload,
                headers={"X-Internal-Key": internal_api_key},
            )
    except Exception as exc:
        logger.exception(
            "fire_notify failed for type=%s — %s",
            payload.get("type"),
            exc,
        )


async def fire_notify_critical(
    payload: Dict[str, Any],
    notification_service_url: str,
    internal_api_key: str,
) -> None:
    """POST to the notification service and raise HTTP 502 on any failure.

    Use for flows where a missing notification is unacceptable
    (e.g. forgot-password reset link).
    """
    if not notification_service_url:
        raise HTTPException(
            status_code=502,
            detail="Notification service is not configured.",
        )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{notification_service_url}{_NOTIFY_SUFFIX}",
                json=payload,
                headers={"X-Internal-Key": internal_api_key},
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
        logger.exception("fire_notify_critical request failed — %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach the notification service.",
        ) from exc


async def fire_deactivate_device_token_by_session(
    session_id: str,
    notification_service_url: str,
    internal_api_key: str,
) -> None:
    """Best-effort PATCH to soft-deactivate device tokens for a session."""
    if not notification_service_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(
                f"{notification_service_url}"
                f"{_DEACTIVATE_BY_SESSION_SUFFIX}/{session_id}",
                headers={"X-Internal-Key": internal_api_key},
            )
    except Exception as exc:
        logger.exception(
            "fire_deactivate_device_token_by_session failed"
            " for session_id=%s — %s",
            session_id,
            exc,
        )


async def fire_remove_device_token_by_session(
    session_id: str,
    notification_service_url: str,
    internal_api_key: str,
) -> None:
    """Best-effort DELETE of all device tokens for a session."""
    if not notification_service_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(
                f"{notification_service_url}{_BY_SESSION_SUFFIX}/{session_id}",
                headers={"X-Internal-Key": internal_api_key},
            )
    except Exception as exc:
        logger.exception(
            "fire_remove_device_token_by_session failed"
            " for session_id=%s — %s",
            session_id,
            exc,
        )


async def fire_remove_device_token_by_user(
    user_id: str,
    notification_service_url: str,
    internal_api_key: str,
) -> None:
    """Best-effort DELETE of all device tokens for a user."""
    if not notification_service_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(
                f"{notification_service_url}{_BY_USER_SUFFIX}/{user_id}",
                headers={"X-Internal-Key": internal_api_key},
            )
    except Exception as exc:
        logger.exception(
            "fire_remove_device_token_by_user failed" " for user_id=%s — %s",
            user_id,
            exc,
        )


async def fire_feedback(
    payload: Dict[str, Any],
    notification_service_url: str,
    internal_api_key: str,
) -> None:
    """Best-effort fire-and-forget POST to
    forward feedback to the GatePass team."""
    if not notification_service_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{notification_service_url}{_FEEDBACK_SUFFIX}",
                json=payload,
                headers={"X-Internal-Key": internal_api_key},
            )
    except Exception as exc:
        logger.exception("fire_feedback failed — %s", exc)
