import logging
from typing import Dict, Optional

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)


class NotificationPreferenceRepository:
    """HTTP wrapper for db-service notification preference endpoints."""

    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.preferences_endpoint = (
            f"{self.base_url}api/v1/notifications/preferences"
        )

    async def get_by_user(self, user_id: str) -> Optional[Dict]:
        return await self.client.async_get(
            url=self.preferences_endpoint, params={"user_id": user_id}
        )

    async def upsert(
        self,
        user_id: str,
        notification_type: NotificationType,
        push_enabled: bool,
        email_enabled: bool,
    ) -> Optional[Dict]:
        payload = {
            "user_id": user_id,
            "notification_type": notification_type.value,
            "push_enabled": push_enabled,
            "email_enabled": email_enabled,
        }
        return await self.client.async_put(
            url=self.preferences_endpoint, json_data=payload
        )
