import logging
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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
                f"{url}api/v1/internal/notify",
                json=payload,
                headers={"X-Internal-Key": settings.INTERNAL_API_KEY},
            )
    except Exception:
        logger.exception("fire_notify failed — notification not delivered")
