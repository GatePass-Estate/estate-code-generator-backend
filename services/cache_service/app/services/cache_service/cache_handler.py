import logging

import redis.asyncio as redis
from pydantic import UUID4

from app.repositories.cache_service.cache_handler import (
    CacheHandlerRepository as Repository,
)
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    ExtendResponse,
    FreezeResponse,
    GetResponse,
    ListResponse,
)

logger = logging.getLogger(__name__)


class CacheHandlerService:
    """Service layer for visitor access codes stored in Redis."""

    def __init__(self, redis_session: redis.Redis) -> None:
        self.repository = Repository(redis_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        """Cache a new visitor access code with lifecycle defaults."""
        return await self.repository.create(request=request)

    async def get(self, code: str) -> GetResponse:
        """Validate and return a visitor access code."""
        return await self.repository.get(code=code)

    async def get_raw(self, code: str) -> dict:
        """
        Return a cached visitor record without validity filtering.

        Intended for internal ownership checks before extend/freeze.
        """
        return await self.repository.get_raw(code=code)

    async def extend(self, code: str) -> ExtendResponse:
        """
        Extend a visitor code once by adding one hour to the period end.

        See repository ``extend`` for one-time semantics and Redis TTL updates.
        """
        return await self.repository.extend(code=code)

    async def toggle_freeze(self, code: str) -> FreezeResponse:
        """Toggle the frozen/paused state of a visitor access code."""
        return await self.repository.toggle_freeze(code=code)

    async def get_all_items_by_user(
        self, user_id: UUID4, estate_id: UUID4
    ) -> ListResponse:
        """List active visitor codes for a resident within an estate."""
        return await self.repository._get_all_items(
            user_id=user_id, estate_id=estate_id
        )

    async def delete(self, code: str) -> bool:
        """Delete a visitor access code from Redis."""
        return await self.repository.delete(code=code)
