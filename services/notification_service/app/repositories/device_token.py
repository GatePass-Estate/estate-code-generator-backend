import logging
from typing import Dict, Optional

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class DeviceTokenRepository:
    """HTTP wrapper for db-service device token endpoints."""

    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.device_tokens_endpoint = (
            f"{self.base_url}api/v1/notifications/device-tokens"
        )

    async def get_by_user(
        self, user_id: str, active_only: bool = True
    ) -> Optional[Dict]:
        return await self.client.async_get(
            url=f"{self.device_tokens_endpoint}/by-user/{user_id}",
            params={"active_only": str(active_only).lower()},
        )

    async def remove_by_token(self, token: str) -> Optional[Dict]:
        return await self.client.async_delete(
            url=f"{self.device_tokens_endpoint}/by-token/{token}"
        )

    async def deactivate_by_session(self, session_id: str) -> Optional[Dict]:
        """Soft-deactivate tokens for a session (called on logout)."""
        return await self.client.async_patch(
            url=f"{self.device_tokens_endpoint}/deactivate-by-session/{session_id}",
            json_data={},
        )

    async def remove_by_session(self, session_id: str) -> Optional[Dict]:
        """Hard-delete tokens for a session (called on explicit revoke)."""
        return await self.client.async_delete(
            url=f"{self.device_tokens_endpoint}/by-session/{session_id}"
        )

    async def remove_by_user(self, user_id: str) -> Optional[Dict]:
        return await self.client.async_delete(
            url=f"{self.device_tokens_endpoint}/by-user/{user_id}"
        )
