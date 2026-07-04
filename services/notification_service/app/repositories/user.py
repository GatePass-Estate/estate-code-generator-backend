import logging
from typing import Dict, Optional

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class UserRepository:
    """HTTP wrapper for db-service user endpoints.

    Used for fan-out resolution and fetching user details for email
    delivery.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.users_endpoint = f"{self.base_url}api/v1/userprofile/users"

    async def search(
        self,
        estate_id: Optional[str] = None,
        role: Optional[str] = None,
        page: int = 1,
        limit: int = 1000,
    ) -> Optional[Dict]:
        """Search users by estate and/or role."""
        params: Dict = {"page": page, "limit": limit}
        if estate_id:
            params["estate_id"] = estate_id
        if role:
            params["role"] = role
        return await self.client.async_get(
            url=f"{self.users_endpoint}/search", params=params
        )

    async def get(self, user_id: str) -> Optional[Dict]:
        """Get a single user by ID."""
        return await self.client.async_get(
            url=f"{self.users_endpoint}/{user_id}"
        )
