import logging
from typing import Optional
from urllib.parse import urlencode

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class TotpRecoveryCodesRepository:
    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.endpoint = (
            f"{settings.DB_SERVICE_URL}" "api/v1/userprofile/totprecoverycodes"
        )

    async def create_recovery_code(self, user_id: str, code_hash: str) -> dict:
        """Creates a new hashed recovery code record."""
        response = await self.client.async_post(
            self.endpoint,
            json_data={"user_id": user_id, "code_hash": code_hash},
        )
        if not response:
            raise HTTPException(
                status_code=500, detail="Recovery code creation failed."
            )
        return response

    async def search_recovery_codes(
        self,
        user_id: Optional[str] = None,
        is_used: Optional[bool] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """Searches recovery codes with optional filters."""
        params: dict = {"page": page, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if is_used is not None:
            params["is_used"] = str(is_used).lower()
        url = f"{self.endpoint}/search?{urlencode(params)}"
        response = await self.client.async_get(url)
        return response or {
            "items": [],
            "total": 0,
            "page": page,
            "limit": limit,
        }

    async def mark_code_used(self, code_id: str, used_at: str) -> None:
        """Sets used_at on a recovery code record."""
        url = f"{self.endpoint}/{code_id}"
        await self.client.async_patch(url, json_data={"used_at": used_at})

    async def delete_all_for_user(self, user_id: str) -> None:
        """Soft-deletes all recovery codes for a user."""
        url = f"{self.endpoint}/user/{user_id}"
        await self.client.async_delete(url)
