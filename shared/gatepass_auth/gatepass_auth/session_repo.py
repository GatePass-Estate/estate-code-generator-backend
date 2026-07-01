from typing import Optional

from gatepass_auth.config import settings
from gatepass_auth.http_client import async_get, async_patch


async def validate_session(session_id: str) -> Optional[dict]:
    """Validates a session via the db-service JOIN endpoint."""
    url = (
        f"{settings.DB_SERVICE_URL}"
        f"api/v1/userprofile/sessions/{session_id}/validate"
    )
    return await async_get(url)


async def update_last_active(session_id: str, last_active_at: str) -> None:
    """Updates last_active_at on a session."""
    url = (
        f"{settings.DB_SERVICE_URL}"
        f"api/v1/userprofile/sessions/{session_id}"
    )
    await async_patch(url, {"last_active_at": last_active_at})
