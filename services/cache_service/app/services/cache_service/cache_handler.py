import logging

import redis.asyncio as redis

from app.repositories.cache_service.cache_handler import (
    CacheHandlerRepository as Repository,
)
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    GetResponse,
)

logger = logging.getLogger(__name__)


class CacheHandlerService:
    """
    Service class for workflows.workflows table.

    Attributes:
        repository: Repository logic for the table.
    """

    def __init__(self, redis_session: redis.Redis) -> None:
        self.repository = Repository(redis_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for creating a new item in the table.

        Returns:
            The CreateResponse object after creating the item in the table.
        """
        return await self.repository.create(request=request)

    async def get(self, code: str) -> GetResponse:
        """
        Get an item by ID.

        Arguments:
            id: The ID of the item to retrieve.

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(code=code)
