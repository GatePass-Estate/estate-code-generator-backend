import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import DatabaseError, NotFoundError
from app.libs.hash_gen import generate_unique_code
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.code_service import (
    CreateRequest,
    CreateResponse,
    GetResponse,
)

logger = logging.getLogger(__name__)


class CodeServiceRepository:
    """
    Repository to operate on workflows.workflows table.
    """

    def __init__(self, ahttp_client: AsyncHttpHandler) -> None:
        """
        Initializes the repository with the provided session.

        Arguments:
            session: The database session.
        """
        self.ahttp_client: AsyncHttpHandler = ahttp_client

    async def _getitem(
        self,
        ahttp_client: AsyncHttpHandler,
        **kwargs,
    ) -> dict:
        """
        Get an item from the table by its ID.

        Arguments:
            session: The database session.
            id: The ID of the item to retrieve.

        Returns:
            Returns an instance of orm_model if the requested item is found.

        Raises:
            NotFoundError: If the requested item is not found.
            DatabaseError: If there's an error during the database operation.
        """
        code = kwargs.get("code", None)
        receiver = kwargs.get("code", None)

        try:
            if receiver == "visitor":
                url = (
                    f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                    f"/cachehandler/{code}"
                )

            response = await ahttp_client.async_get(url)
            return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _setitem(
        self,
        ahttp_client: AsyncHttpHandler,
        request: CreateRequest,
        receiver: str,
    ) -> CreateResponse:
        """
        Create a new record in the database.

        Args:
            session (AsyncSession): The database session.
            request (TableModel): The record to be created in the database.

        Returns:
            TableModel: Returns an instance of orm_model containing the
            created record.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
        try:
            if receiver == "visitor":
                url = (
                    f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                    f"/cachehandler/"
                )

            visit_data = request.model_dump()
            code = generate_unique_code(
                user_id=visit_data.get("user_id"),
                visitor_name=visit_data.get("visitor_name"),
                relationship=visit_data.get("relationship"),
                date_of_visit=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
            visit_data["hashed_code"] = code
            data = {"hashed_code": code, "visit_data": visit_data}
            response = await ahttp_client.async_post(url, json_data=data)
            return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def create(
        self, request: CreateRequest, receiver: str
    ) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for creating a new item in the table.

        Returns:
            The CreateResponse object after creating the item in the table.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
        try:
            # Create the record in the database
            response = await self._setitem(
                ahttp_client=self.ahttp_client,
                request=request,
                receiver=receiver,
            )
            created_record = CreateResponse.model_validate(response)
            return created_record
        except DatabaseError as e:
            message = "Database error in creating the prompt template"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, code: str, receiver: str) -> GetResponse:
        """
        Get an item by ID.

        Arguments:
            id: The ID of the item to retrieve.

        Returns:
            A GetResponse object after retrieving the item by id.

        Raises:
            DatabaseError: If there's an error during the database operation.
            NotFoundError: If the item with the provided ID is not found.
        """
        try:
            # Get the record from the database
            record = await self._getitem(
                ahttp_client=self.ahttp_client, code=code, receiver=receiver
            )
            # Convert the record to a GET schema model
            return GetResponse.model_validate(record, from_attributes=True)
        except NotFoundError as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in getting a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e
