import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_profile.sessions import (
    SessionsRepository as Repository,
)
from app.schemas.user_profile.sessions import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)


class SessionsService:
    """
    Service class for Sessions table.

    Attributes:
        repository: Repository logic for the table.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for creating a new item in the table.

        Returns:
            The CreateResponse object after creating the item in the table.
        """
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        """
        Soft Deletes an item from the table.

        Arguments:
            id: The ID of the item to delete.
        Returns:
            The DeleteResponse object after deleting the item from the table.
        """
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        """
        Get an item by ID.

        Arguments:
            id: The ID of the item to retrieve.

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(id=id)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        """
        Update an existing item with matching id.

        Arguments:
            id: The ID of the item to update.
            request: The request body for updating a item matching the id.

        Returns:
            An UpdateResponse object after updating the item in the table.

        Raises:
            NotFoundError: If the item with the provided ID is not found.
            DatabaseError: If there's an error during the database operation.
        """
        return await self.repository.update(id=id, request=request)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 10
    ) -> ListResponse:
        """
        Filters items based on the provided search criteria and returns
        a list of them meeting the criteria.

        Arguments:
            request: The request body for searching items.

        Returns:
            A ListResponse object containing all the items found from the
                  table
            which match the requested criteria.
        """
        return await self.repository.search(
            request=request, page=page, limit=limit
        )

    async def delete_all_for_user(self, user_id: str) -> None:
        """
        Soft-deletes all non-deleted sessions belonging to a given user.

        Arguments:
            user_id: The ID of the user whose sessions should be deleted.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
        return await self.repository.delete_all_for_user(user_id=user_id)
