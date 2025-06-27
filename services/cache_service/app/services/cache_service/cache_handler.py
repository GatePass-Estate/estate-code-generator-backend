import logging

import redis.asyncio as redis
from pydantic import UUID4

from app.repositories.cache_service.cache_handler import (
    CacheHandlerRepository as Repository,
)
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    ListResponse,
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
            code: The generated access code to be retrieved.

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(code=code)

    async def get_all_items_by_user(self, user_id: UUID4) -> ListResponse:
        """
        List all items in the table for a given user.

        Arguments:
            user_id: The ID of the user to retrieve items for.

        Returns:
            A ListResponse object after retrieving the items for the user.
        """
        return await self.repository._get_all_items(user_id=user_id)

    async def delete(self, code: str) -> bool:
        """
        Delete an item by ID.

        Arguments:
            code: The generated access code to be deleted.

        Returns:
            A boolean indicating whether the item was deleted successfully.
        """
        return await self.repository.delete(code=code)
