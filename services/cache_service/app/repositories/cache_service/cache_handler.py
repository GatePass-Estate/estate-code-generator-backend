import json
import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from fastapi import HTTPException

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

    def _format_datetime(self, dt: datetime) -> str:
        ms = int(dt.microsecond / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d}+0000"

    async def _getitem(
        self,
        session: redis.Redis,
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
        try:
            data = await session.get(code)

            if data:
                result = json.loads(data)
                valid_until = result.get("valid_until")

                if valid_until:
                    valid_until = datetime.strptime(
                        valid_until, "%Y-%m-%d %H:%M:%S.%f%z"
                    )
                    now = datetime.now(timezone.utc)

                    if now > valid_until:
                        raise HTTPException(
                            status_code=400, detail="Cached entry has expired"
                        )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Expiry timestamp missing in cached data",
                    )
                result["is_expired"] = False
                return result
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
            code = request.hashed_code
            # visit_data = request.visit_data.model_dump_json()
            visit_data = request.visit_data.model_dump()
            valid_until = datetime.now(timezone.utc) + timedelta(hours=1)
            valid_until = self._format_datetime(valid_until)
            visit_data["valid_until"] = valid_until

            visit_data = json.dumps(visit_data)
            await session.set(code, visit_data, ex=3600)
            response = {"hashed_code": code, "valid_until": valid_until}
            return response
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
            response = await self._setitem(
                session=self.session, request=request
            )
            created_record = CreateResponse.model_validate(response)
            return created_record
        except DatabaseError as e:
            message = "Database error in creating the prompt template"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, code: str) -> GetResponse:
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
            record = await self._getitem(session=self.session, code=code)
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
