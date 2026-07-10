import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class SessionRepository:
    def __init__(self, http_client: AsyncHttpHandler):
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.sessions_endpoint = f"{self.base_url}api/v1/userprofile/sessions"

    async def create_session(
        self,
        user_id: str,
        ip_address: Optional[str],
        device_name: Optional[str],
        expires_at: datetime,
        is_2fa_verified: bool = False,
    ) -> dict:
        """Creates a new session record in the db-service."""
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "ip_address": ip_address,
            "device_name": device_name,
            "last_active_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_2fa_verified": is_2fa_verified,
        }
        response = await self.client.async_post(
            self.sessions_endpoint, json_data=payload
        )
        if not response:
            raise HTTPException(
                status_code=500, detail="Session creation failed."
            )
        logger.info(f"Session created: {response['id']}")
        return response

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieves a session by ID."""
        url = f"{self.sessions_endpoint}/{session_id}"
        response = await self.client.async_get(url)
        return response or None

    async def update_session(
        self, session_id: str, data: dict
    ) -> Optional[dict]:
        """Updates a session (e.g. last_active_at, is_2fa_verified)."""
        url = f"{self.sessions_endpoint}/{session_id}"
        return await self.client.async_patch(url, json_data=data)

    async def delete_session(self, session_id: str) -> Optional[dict]:
        """Soft-deletes a single session."""
        url = f"{self.sessions_endpoint}/{session_id}"
        response = await self.client.async_delete(url)
        if not response:
            raise HTTPException(status_code=404, detail="Session not found.")
        return response

    async def delete_all_sessions_for_user(
        self, user_id: str
    ) -> Optional[dict]:
        """Soft-deletes all sessions for a user."""
        url = f"{self.sessions_endpoint}/user/{user_id}"
        response = await self.client.async_delete(url)
        return response

    async def validate_session(self, session_id: str) -> Optional[dict]:
        """
        Validates a session via the db-service JOIN endpoint.
        Returns combined session + user data, or None if not found.
        """
        url = f"{self.sessions_endpoint}/{session_id}/validate"
        response = await self.client.async_get(url)
        return response or None

    async def enable_biometric(self, session_id: str, token_hash: str) -> None:
        """Store biometric token hash on a session."""
        url = f"{self.sessions_endpoint}/{session_id}"
        await self.client.async_patch(
            url, json_data={"biometric_token_hash": token_hash}
        )

    async def get_session_by_biometric_hash(
        self, token_hash: str
    ) -> Optional[dict]:
        """Look up an active session by its biometric token hash."""
        url = (
            f"{self.sessions_endpoint}/by-biometric-token"
            f"?hash={token_hash}"
        )
        return await self.client.async_get(url)

    async def rotate_biometric_token(
        self,
        session_id: str,
        new_hash: str,
        new_expires_at: datetime,
    ) -> None:
        """Swap biometric hash and extend session expiry atomically."""
        url = f"{self.sessions_endpoint}/{session_id}"
        await self.client.async_patch(
            url,
            json_data={
                "biometric_token_hash": new_hash,
                "expires_at": new_expires_at.isoformat(),
            },
        )

    async def disable_biometric(self, session_id: str) -> None:
        """Clear the biometric token from a session."""
        url = f"{self.sessions_endpoint}/{session_id}"
        await self.client.async_patch(
            url, json_data={"biometric_token_hash": None}
        )

    async def search_sessions(
        self,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        is_2fa_verified: Optional[bool] = None,
        last_active_after: Optional[datetime] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """Searches sessions with optional filters."""
        params: dict = {"page": page, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if ip_address:
            params["ip_address"] = ip_address
        if is_2fa_verified is not None:
            params["is_2fa_verified"] = str(is_2fa_verified).lower()
        if last_active_after:
            params["last_active_after"] = last_active_after.isoformat()

        url = f"{self.sessions_endpoint}/search?{urlencode(params)}"
        response = await self.client.async_get(url)
        return response or {
            "items": [],
            "total": 0,
            "page": page,
            "limit": limit,
        }
