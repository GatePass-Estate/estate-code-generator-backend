import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)


class NotificationRepository:
    """HTTP wrapper for db-service notification endpoints."""

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.notifications_endpoint = f"{self.base_url}api/v1/notifications"

    async def create(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        payload = {
            "user_id": user_id,
            "type": notification_type.value,
            "title": title,
            "body": body,
            "payload": metadata,
        }
        return await self.client.async_post(
            url=self.notifications_endpoint, json_data=payload
        )

    async def create_bulk(
        self, rows: List[Dict[str, Any]]
    ) -> Optional[List[Dict]]:
        return await self.client.async_post(
            url=f"{self.notifications_endpoint}/bulk", json_data=rows
        )

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
        return await self.client.async_get(
            url=self.notifications_endpoint, params=params
        )

    async def unread_count(
        self, user_id: str, max_age_days: int = 90
    ) -> Optional[Dict]:
        return await self.client.async_get(
            url=f"{self.notifications_endpoint}/unread-count",
            params={"user_id": user_id, "max_age_days": max_age_days},
        )

    async def mark_read(
        self, notification_id: str, user_id: str
    ) -> Optional[Dict]:
        return await self.client.async_patch(
            url=f"{self.notifications_endpoint}/{notification_id}/read",
            params={"user_id": user_id},
        )

    async def mark_all_read(self, user_id: str) -> Optional[Dict]:
        return await self.client.async_patch(
            url=f"{self.notifications_endpoint}/read-all",
            params={"user_id": user_id},
        )

    async def delete_by_id(
        self, notification_id: str, user_id: str
    ) -> Optional[Dict]:
        return await self.client.async_delete(
            url=f"{self.notifications_endpoint}/{notification_id}",
            params={"user_id": user_id},
        )

    async def delete_all(self, user_id: str) -> Optional[Dict]:
        return await self.client.async_delete(
            url=f"{self.notifications_endpoint}/by-user/{user_id}",
        )
