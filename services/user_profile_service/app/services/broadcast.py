from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.libs.notify import fire_notify
from app.libs.role_permissions import check_permission
from app.repositories.broadcast import BroadcastRepository
from app.repositories.estate import EstateRepository
from app.repositories.user import UserRepository
from app.schemas.broadcast import (
    BroadcastCategory,
    BroadcastCreatePayload,
    BroadcastCreateResponse,
    BroadcastDeleteResponse,
    BroadcastItem,
    BroadcastListResponse,
    BroadcastPriority,
    BroadcastReadResponse,
    BroadcastUpdateResponse,
    CreateBroadcastRequest,
    DismissAllResponse,
    UnreadBroadcastCountResponse,
    UpdateBroadcastRequest,
)
from app.schemas.estate import EstateType, SearchEstateRequest

logger = logging.getLogger(__name__)

_PRIORITY_TO_NOTIFICATION_TYPE = {
    BroadcastPriority.HIGH: "BROADCAST_HIGH",
    BroadcastPriority.MEDIUM: "BROADCAST_MEDIUM",
}


_ROOT_DEFAULT_SENDER = "GatePass Team"


class BroadcastService:
    def __init__(
        self,
        broadcast_repo: BroadcastRepository,
        estate_repo: EstateRepository,
        user_repo: UserRepository,
        http_client: AsyncHttpHandler,
    ) -> None:
        self.repo = broadcast_repo
        self.estate_repo = estate_repo
        self.user_repo = user_repo
        self.http_client = http_client

    async def _resolve_sender_name(
        self,
        requester_id: str,
        is_root: bool,
        provided_name: Optional[str],
    ) -> str:
        if provided_name:
            return provided_name
        if is_root:
            return _ROOT_DEFAULT_SENDER
        user = await self.user_repo.get_user_by_id(requester_id)
        if user:
            return f"{user.first_name} {user.last_name}".strip()
        return ""

    async def _resolve_target_estates(
        self, request: CreateBroadcastRequest
    ) -> List[str]:
        """Resolve the list of estate IDs for a root broadcast."""
        if request.target_estate_ids:
            return [str(eid) for eid in request.target_estate_ids]

        estate_ids: List[str] = []
        page = 1
        limit = 100
        while True:
            search = SearchEstateRequest(
                state=request.target_state,
                lga=request.target_lga,
                estate_type=(
                    EstateType(request.target_estate_type)
                    if request.target_estate_type
                    else None
                ),
                is_active=True,
                page=page,
                limit=limit,
            )
            result = await self.estate_repo.search_estates(request=search)
            if not result or not result.items:
                break
            estate_ids.extend(item.id for item in result.items)
            if len(result.items) < limit:
                break
            page += 1
        return estate_ids

    def _assert_visible(
        self,
        broadcast: BroadcastItem,
        requester_estate_id: Optional[str],
        requester_role: str,
    ) -> None:
        """
        Raise 404 if the broadcast is not visible to this user.

        A broadcast is visible when:
        - Its estate_id matches the user's estate OR is None (global)
        - The user's role is in the audience list
        """
        is_global = broadcast.estate_id is None
        in_estate = broadcast.estate_id == requester_estate_id
        if not (is_global or in_estate):
            raise HTTPException(status_code=404, detail="Broadcast not found")
        if requester_role not in broadcast.audience:
            raise HTTPException(status_code=404, detail="Broadcast not found")

    async def create_and_deliver(
        self,
        request: CreateBroadcastRequest,
        *,
        requester_id: str,
        requester_role: str,
        requester_estate_id: Optional[str],
    ) -> BroadcastCreateResponse:
        """
        Persist a broadcast and fire push/email notifications based on
        priority.

        Permission is checked against the role_permission table.
        Root (no estate_id) → estate_id stored as None; targeting resolved
        from request fields.
        Admin → estate_id forced to their own estate.
        """
        can_broadcast = await check_permission(
            self.http_client, requester_role, "can_create_broadcast"
        )
        if not can_broadcast:
            raise HTTPException(
                status_code=403,
                detail="Your role does not have permission to "
                "create broadcasts.",
            )

        is_root = requester_estate_id is None
        if not is_root and any(
            [
                request.target_estate_ids,
                request.target_state,
                request.target_lga,
                request.target_estate_type,
            ]
        ):
            raise HTTPException(
                status_code=403,
                detail="Cross-estate targeting is only available to root.",
            )

        if request.category == BroadcastCategory.AD:
            if not is_root:
                raise HTTPException(
                    status_code=403,
                    detail="Only root can create AD-category broadcasts.",
                )
            if not request.expires_at:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "expires_at is required for AD-category broadcasts."
                    ),
                )

        sender_name = await self._resolve_sender_name(
            requester_id=requester_id,
            is_root=is_root,
            provided_name=request.sender_name,
        )

        payload = BroadcastCreatePayload(
            estate_id=requester_estate_id,
            sender_id=requester_id,
            title=request.title,
            message=request.message,
            category=request.category.value,
            priority=request.priority.value,
            audience=request.audience,
            sender_name=sender_name,
            attachment_url=request.attachment_url,
            expires_at=request.expires_at,
        )
        broadcast = await self.repo.create(payload)

        notification_type = _PRIORITY_TO_NOTIFICATION_TYPE.get(
            request.priority
        )
        if notification_type is None:
            # LOW priority — in-app only, no push/email
            return broadcast

        notify_base = {
            "type": notification_type,
            "title": request.title,
            "body": request.message,
            "metadata": {
                "broadcast_id": broadcast.id,
                "sender_name": request.sender_name,
                "tab": "broadcasts",
            },
        }

        if not is_root:
            await fire_notify(
                {
                    **notify_base,
                    "fan_out": {
                        "estate_id": requester_estate_id,
                        "roles": request.audience,
                    },
                }
            )
        else:
            estate_ids = await self._resolve_target_estates(request)
            for eid in estate_ids:
                await fire_notify(
                    {
                        **notify_base,
                        "fan_out": {
                            "estate_id": str(eid),
                            "roles": request.audience,
                        },
                    }
                )

        return broadcast

    async def list_for_user(
        self,
        *,
        user_id: str,
        estate_id: str,
        roles: List[str],
        page: int = 1,
        limit: int = 20,
    ) -> BroadcastListResponse:
        """
        List broadcasts visible to a user, with dismissed ones excluded
        at the DB level and remaining items annotated with is_read.
        """
        result = await self.repo.search(
            estate_id=estate_id,
            audience=roles,
            status=True,
            exclude_expired=True,
            include_global=True,
            exclude_dismissed_by_user_id=user_id,
            page=page,
            limit=limit,
        )
        broadcast_ids = [item.id for item in result.items]
        read_ids = await self.repo.get_read_ids(
            user_id=user_id, broadcast_ids=broadcast_ids
        )
        items = [
            item.model_copy(update={"is_read": item.id in read_ids})
            for item in result.items
        ]
        return result.model_copy(update={"items": items})

    async def get(
        self,
        broadcast_id: str,
        *,
        requester_estate_id: Optional[str],
        requester_role: str,
    ) -> BroadcastItem:
        broadcast = await self.repo.get_by_id(broadcast_id)
        self._assert_visible(broadcast, requester_estate_id, requester_role)
        return broadcast

    async def mark_read(
        self,
        broadcast_id: str,
        user_id: str,
        *,
        requester_estate_id: Optional[str],
        requester_role: str,
    ) -> BroadcastReadResponse:
        broadcast = await self.repo.get_by_id(broadcast_id)
        self._assert_visible(broadcast, requester_estate_id, requester_role)
        return await self.repo.mark_read(
            broadcast_id=broadcast_id, user_id=user_id
        )

    async def dismiss(
        self,
        broadcast_id: str,
        user_id: str,
        *,
        requester_estate_id: Optional[str],
        requester_role: str,
    ) -> BroadcastReadResponse:
        """Dismiss a single BROADCAST-category broadcast for a user."""
        broadcast = await self.repo.get_by_id(broadcast_id)
        self._assert_visible(broadcast, requester_estate_id, requester_role)
        if broadcast.category == BroadcastCategory.AD.value:
            raise HTTPException(
                status_code=400,
                detail="AD-category broadcasts cannot be dismissed.",
            )
        return await self.repo.dismiss(
            broadcast_id=broadcast_id, user_id=user_id
        )

    async def dismiss_all(
        self, user_id: str, estate_id: str
    ) -> DismissAllResponse:
        """Dismiss all BROADCAST-category broadcasts for a user."""
        return await self.repo.dismiss_all(
            user_id=user_id, estate_id=estate_id
        )

    async def unread_count(
        self, user_id: str, estate_id: str, roles: List[str]
    ) -> UnreadBroadcastCountResponse:
        count = await self.repo.unread_count(
            user_id=user_id, estate_id=estate_id, roles=roles
        )
        return UnreadBroadcastCountResponse(count=count)

    async def update(
        self,
        broadcast_id: str,
        payload: UpdateBroadcastRequest,
        *,
        requester_id: str,
        requester_role: str,
    ) -> BroadcastUpdateResponse:
        broadcast = await self.repo.get_by_id(broadcast_id)
        is_owner = broadcast.sender_id == requester_id
        is_root = requester_role == "root"
        if not (is_owner or is_root):
            raise HTTPException(
                status_code=403,
                detail="Only the sender or root can update this broadcast.",
            )
        return await self.repo.update(broadcast_id, payload)

    async def delete(
        self,
        broadcast_id: str,
        *,
        requester_id: str,
        requester_role: str,
    ) -> BroadcastDeleteResponse:
        broadcast = await self.repo.get_by_id(broadcast_id)
        is_owner = broadcast.sender_id == requester_id
        is_root = requester_role == "root"
        if not (is_owner or is_root):
            raise HTTPException(
                status_code=403,
                detail="Only the sender or root can delete this broadcast.",
            )
        return await self.repo.delete(broadcast_id)
