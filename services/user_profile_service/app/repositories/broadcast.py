from __future__ import annotations

import logging
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.broadcast import (
    BroadcastCreatePayload,
    BroadcastCreateResponse,
    BroadcastDeleteResponse,
    BroadcastItem,
    BroadcastListResponse,
    BroadcastReadResponse,
    BroadcastUpdateResponse,
    DismissAllResponse,
    UpdateBroadcastRequest,
)

logger = logging.getLogger(__name__)

_BROADCASTS_ENDPOINT = "api/v1/userprofile/broadcasts"
_BROADCAST_READS_ENDPOINT = "api/v1/userprofile/broadcast_reads"


class BroadcastRepository:
    def __init__(self, http_client: AsyncHttpHandler) -> None:
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL.rstrip("/")
        self.endpoint = f"{self.base_url}/{_BROADCASTS_ENDPOINT}"
        self.reads_endpoint = f"{self.base_url}/{_BROADCAST_READS_ENDPOINT}"

    async def create(
        self, payload: BroadcastCreatePayload
    ) -> BroadcastCreateResponse:
        data = await self.client.async_post(
            self.endpoint,
            json_data=payload.model_dump(mode="json"),
        )
        return BroadcastCreateResponse.model_validate(data)

    async def get_by_id(self, broadcast_id: str) -> BroadcastItem:
        data = await self.client.async_get(f"{self.endpoint}/{broadcast_id}")
        return BroadcastItem.model_validate(data)

    async def search(
        self,
        *,
        estate_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[bool] = None,
        audience: Optional[List[str]] = None,
        exclude_expired: Optional[bool] = None,
        include_global: Optional[bool] = None,
        exclude_dismissed_by_user_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> BroadcastListResponse:
        params: dict = {"page": page, "limit": limit}
        if estate_id:
            params["estate_id"] = estate_id
        if sender_id:
            params["sender_id"] = sender_id
        if priority:
            params["priority"] = priority
        if category:
            params["category"] = category
        if status is not None:
            params["status"] = status
        if exclude_expired is not None:
            params["exclude_expired"] = exclude_expired
        if include_global is not None:
            params["include_global"] = include_global
        if exclude_dismissed_by_user_id is not None:
            params["exclude_dismissed_by_user_id"] = (
                exclude_dismissed_by_user_id
            )
        parts = list(params.items())
        if audience:
            parts += [("audience", r) for r in audience]
        url = f"{self.endpoint}/search?{urlencode(parts)}"
        data = await self.client.async_get(url)
        if not data:
            return BroadcastListResponse(
                total=0, page=page, limit=limit, items=[]
            )
        return BroadcastListResponse.model_validate(data)

    async def update(
        self, broadcast_id: str, payload: UpdateBroadcastRequest
    ) -> BroadcastUpdateResponse:
        data = await self.client.async_patch(
            f"{self.endpoint}/{broadcast_id}",
            json_data=payload.model_dump(mode="json", exclude_unset=True),
        )
        if not data:
            raise HTTPException(
                status_code=500, detail="Failed to update broadcast"
            )
        return BroadcastUpdateResponse.model_validate(data)

    async def delete(self, broadcast_id: str) -> BroadcastDeleteResponse:
        data = await self.client.async_delete(
            f"{self.endpoint}/{broadcast_id}"
        )
        if not data:
            raise HTTPException(
                status_code=500, detail="Failed to delete broadcast"
            )
        return BroadcastDeleteResponse.model_validate(data)

    async def mark_read(
        self, broadcast_id: str, user_id: str
    ) -> BroadcastReadResponse:
        data = await self.client.async_post(
            self.reads_endpoint,
            json_data={"broadcast_id": broadcast_id, "user_id": user_id},
        )
        return BroadcastReadResponse.model_validate(data)

    async def dismiss(
        self, broadcast_id: str, user_id: str
    ) -> BroadcastReadResponse:
        data = await self.client.async_post(
            f"{self.reads_endpoint}/dismiss",
            json_data={"broadcast_id": broadcast_id, "user_id": user_id},
        )
        return BroadcastReadResponse.model_validate(data)

    async def dismiss_all(
        self, user_id: str, estate_id: str
    ) -> DismissAllResponse:
        data = await self.client.async_post(
            f"{self.reads_endpoint}/dismiss-all",
            json_data={"user_id": user_id, "estate_id": estate_id},
        )
        return DismissAllResponse.model_validate(data)

    async def get_read_ids(
        self, user_id: str, broadcast_ids: List[str]
    ) -> set:
        """Return the set of broadcast IDs the user has already read."""
        if not broadcast_ids:
            return set()
        params = urlencode(
            [("user_id", user_id)]
            + [("broadcast_id", bid) for bid in broadcast_ids]
        )
        url = f"{self.reads_endpoint}?{params}"
        response = await self.client.async_get(url)
        items = response.get("items", []) if response else []
        return {item["broadcast_id"] for item in items}

    async def unread_count(
        self, user_id: str, estate_id: str, roles: List[str]
    ) -> int:
        params = urlencode(
            [("user_id", user_id), ("estate_id", estate_id)]
            + [("roles", r) for r in roles]
        )
        url = f"{self.reads_endpoint}/unread-count?{params}"
        response = await self.client.async_get(url)
        return (response or {}).get("count", 0)
