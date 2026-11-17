from typing import Any, Dict

from gatepass_notify import fire_notify as _fire_notify

from app.core.config import settings


async def fire_notify(payload: Dict[str, Any]) -> None:
    """POST to notification-service ``/internal/notify`` (best-effort)."""
    await _fire_notify(
        payload,
        settings.NOTIFICATION_SERVICE_URL,
        settings.INTERNAL_API_KEY,
    )
