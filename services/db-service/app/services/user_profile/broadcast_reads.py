import logging
from typing import List
from uuid import UUID

from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_profile.broadcast_reads import (
    BroadcastReadsRepository as Repository,
)
from app.schemas.user_profile.broadcast_reads import (
    CreateRequest,
    CreateResponse,
    DismissAllRequest,
    DismissRequest,
    ListResponse,
    SearchRequest,
)
from app.schemas.user_profile.notifications import UnreadCountResponse

logger = logging.getLogger(__name__)


class BroadcastReadsService:
    """Service class for the broadcast_reads table."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def mark_read(self, request: CreateRequest) -> CreateResponse:
        """Mark a broadcast as read for the given user (idempotent)."""
        return await self.repository.upsert(request=request)

    async def dismiss(self, request: DismissRequest) -> CreateResponse:
        """Dismiss a single broadcast for a user (idempotent)."""
        return await self.repository.dismiss(request=request)

    async def dismiss_all(self, request: DismissAllRequest) -> dict:
        """Dismiss all BROADCAST-category broadcasts for a user."""
        dismissed = await self.repository.dismiss_all(request=request)
        return {"dismissed": dismissed}

    async def get_read_ids_for_user(
        self, user_id: UUID4, broadcast_ids: List[UUID]
    ) -> List[UUID]:
        """Return which of the given broadcast IDs the user has read."""
        return await self.repository.get_read_ids_for_user(
            user_id=user_id, broadcast_ids=broadcast_ids
        )

    async def unread_count(
        self, user_id: UUID4, estate_id: UUID4, roles: List[str]
    ) -> UnreadCountResponse:
        """Count broadcasts visible to the user that are unread/undismissed."""
        return await self.repository.unread_count(
            user_id=user_id, estate_id=estate_id, roles=roles
        )

    async def search(self, request: SearchRequest) -> ListResponse:
        """List broadcast read records filtered by broadcast_id / user_id."""
        return await self.repository.search(request=request)
