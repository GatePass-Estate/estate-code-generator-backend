from typing import Any, Dict

from gatepass_notify import (
    fire_deactivate_device_token_by_session as _deactivate_by_session,
    fire_notify as _fire_notify,
    fire_notify_critical as _fire_notify_critical,
    fire_remove_device_token_by_session as _remove_by_session,
    fire_remove_device_token_by_user as _remove_by_user,
)

from app.core.config import settings


async def fire_notify(payload: Dict[str, Any]) -> None:
    await _fire_notify(
        payload,
        settings.NOTIFICATION_SERVICE_URL,
        settings.INTERNAL_API_KEY,
    )


async def fire_notify_critical(payload: Dict[str, Any]) -> None:
    await _fire_notify_critical(
        payload,
        settings.NOTIFICATION_SERVICE_URL,
        settings.INTERNAL_API_KEY,
    )


async def fire_deactivate_device_token_by_session(
    session_id: str,
) -> None:
    await _deactivate_by_session(
        session_id,
        settings.NOTIFICATION_SERVICE_URL,
        settings.INTERNAL_API_KEY,
    )


async def fire_remove_device_token_by_session(
    session_id: str,
) -> None:
    await _remove_by_session(
        session_id,
        settings.NOTIFICATION_SERVICE_URL,
        settings.INTERNAL_API_KEY,
    )


async def fire_remove_device_token_by_user(user_id: str) -> None:
    await _remove_by_user(
        user_id,
        settings.NOTIFICATION_SERVICE_URL,
        settings.INTERNAL_API_KEY,
    )
