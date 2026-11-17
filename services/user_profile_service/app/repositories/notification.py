import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)

_NOTIFICATIONS_ENDPOINT = "api/v1/notifications"


class NotificationRepository:
    """HTTP wrapper for db-service notification endpoints (user-facing only)."""

    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.endpoint = f"{self.base_url}{_NOTIFICATIONS_ENDPOINT}"

    async def list_for_user(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        max_age_days: int = 90,
        page: int = 1,
        limit: int = 20,
    ) -> Optional[Dict]:
        params: Dict[str, Any] = {
            "user_id": user_id,
            "max_age_days": max_age_days,
            "page": page,
            "limit": limit,
        }
        if is_read is not None:
            params["is_read"] = is_read
        return await self.client.async_get(url=self.endpoint, params=params)

    async def unread_count(
        self, user_id: str, max_age_days: int = 90
    ) -> Optional[Dict]:
        return await self.client.async_get(
            url=f"{self.endpoint}/unread-count",
            params={"user_id": user_id, "max_age_days": max_age_days},
        )

    async def mark_read(
        self, notification_id: str, user_id: str
    ) -> Optional[Dict]:
        qs = urlencode({"user_id": user_id})
        return await self.client.async_patch(
            url=f"{self.endpoint}/{notification_id}/read?{qs}",
        )

    async def mark_all_read(self, user_id: str) -> Optional[Dict]:
        qs = urlencode({"user_id": user_id})
        return await self.client.async_patch(
            url=f"{self.endpoint}/read-all?{qs}",
        )

    async def delete_by_id(
        self, notification_id: str, user_id: str
    ) -> Optional[Dict]:
        qs = urlencode({"user_id": user_id})
        return await self.client.async_delete(
            url=f"{self.endpoint}/{notification_id}?{qs}",
        )

    async def delete_all(self, user_id: str) -> Optional[Dict]:
        return await self.client.async_delete(
            url=f"{self.endpoint}/by-user/{user_id}",
        )

    async def purge_old(self, older_than_days: int) -> Optional[Dict]:
        qs = urlencode({"older_than_days": older_than_days})
        return await self.client.async_post(
            url=f"{self.endpoint}/purge?{qs}",
        )
