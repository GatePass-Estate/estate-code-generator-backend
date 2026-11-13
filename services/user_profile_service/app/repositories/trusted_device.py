import logging
from typing import Optional
from urllib.parse import urlencode

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class TrustedDeviceRepository:
    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.endpoint = f"{self.base_url}api/v1/userprofile/trusted_devices"

    async def create_device(
        self,
        user_id: str,
        token_hash: str,
        device_label: Optional[str],
        ip_address: Optional[str],
        last_seen_at: str,
        expires_at: str,
    ) -> dict:
        """Creates a new trusted device record in the db-service."""
        payload = {
            "user_id": user_id,
            "token_hash": token_hash,
            "device_label": device_label,
            "ip_address": ip_address,
            "last_seen_at": last_seen_at,
            "expires_at": expires_at,
        }
        response = await self.client.async_post(
            self.endpoint, json_data=payload
        )
        if not response:
            raise HTTPException(
                status_code=500, detail="Trusted device creation failed."
            )
        return response

    async def get_by_token_hash(self, token_hash: str) -> Optional[dict]:
        """Look up a trusted device by its token hash."""
        url = f"{self.endpoint}/by-token-hash?hash={token_hash}"
        return await self.client.async_get(url)

    async def update_device(
        self, device_id: str, data: dict
    ) -> Optional[dict]:
        """Updates a trusted device (e.g. last_seen_at)."""
        url = f"{self.endpoint}/{device_id}"
        return await self.client.async_patch(url, json_data=data)

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Revokes all trusted devices for a user."""
        url = f"{self.endpoint}/user/{user_id}"
        await self.client.async_delete(url)

    async def search_devices(
        self,
        user_id: Optional[str] = None,
        token_hash: Optional[str] = None,
        is_revoked: Optional[bool] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """Searches trusted devices with optional filters."""
        params: dict = {"page": page, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if token_hash:
            params["token_hash"] = token_hash
        if is_revoked is not None:
            params["is_revoked"] = str(is_revoked).lower()

        url = f"{self.endpoint}/search?{urlencode(params)}"
        response = await self.client.async_get(url)
        return response or {
            "items": [],
            "total": 0,
            "page": page,
            "limit": limit,
        }

    async def delete_device(self, device_id: str) -> None:
        """Soft-deletes a single trusted device."""
        url = f"{self.endpoint}/{device_id}"
        await self.client.async_delete(url)
