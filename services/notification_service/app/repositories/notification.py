import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class NotificationRepository:
    """HTTP wrapper for db-service notification endpoints."""

    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.notifications_endpoint = f"{self.base_url}api/v1/notifications"

    async def create_bulk(
        self, rows: List[Dict[str, Any]]
    ) -> Optional[List[Dict]]:
        return await self.client.async_post(
            url=f"{self.notifications_endpoint}/bulk", json_data=rows
        )
