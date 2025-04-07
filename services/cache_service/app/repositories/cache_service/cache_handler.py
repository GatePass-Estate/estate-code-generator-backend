import json
import logging

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import UUID4

from app.core.exceptions import DatabaseError, NotFoundError
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    GetResponse,
)

logger = logging.getLogger(__name__)


class CacheHandlerRepository:
    """
    Repository to operate on workflows.workflows table.
    """

    def __init__(self, session: redis.Redis) -> None:
        """
        Initializes the repository with the provided session.

        Arguments:
            session: The database session.
        """
        self.session: redis.Redis = session

    async def _getitem(
        self,
        session: redis.Redis,
        **kwargs,
    ) -> GetResponse:
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
        try:
            data = session.get(code)
            if data:
                return json.loads(data)
            else:
                raise HTTPException(status_code=404, detail="Key not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _setitem(
        self,
        session: redis.Redis,
        request: CreateRequest,
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
            # Save the JSON data as a string in Redis
            session.set(json_data.key, json.dumps(json_data.data))  # noqa
            return {"message": "Data cached successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def create(self, request: CreateRequest) -> CreateResponse:
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
            record = await self._setitem(
                session=self.session,
                request=TableModel(  # noqa
                    **request.model_dump(exclude_unset=True)
                ),  # convert the request to a database model instance.
            )
            # convert the record to a CREATE schema model.
            created_record = CreateResponse.model_validate(record.__dict__)
            # return the created record.
            return created_record
        except DatabaseError as e:
            message = "Database error in creating the prompt template"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, id: UUID4) -> GetResponse:
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
            record = await self._getitem(session=self.session, id=id)
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
