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
            session: The redis session.
            code: The generated access code to be retrieved.

        Returns:
            Returns a json object of the requested item is found.

        Raises:
            HTTPException: If item is not found, cached extry is expired, time-
                stamp is missing, or unexpected error occured during retrieval.
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
    ) -> dict:
        """
        Create a new record in the database.

        Args:
            session (AsyncSession): The redis session.
            request (CreateRequest): The record to be persisted to the cache.

        Returns:
            Returns a response dict with information on the performed insert.

        Raises:
            HTTPException: If there's an error during the insert operation.
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
            request (CreateRequest): The record to be persisted to the cache.

        Returns:
            The CreateResponse object after inserting the item into the cache.

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
            message = "REDIS DB Error while inserting item into Cache"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, code: str) -> GetResponse:
        """
        Get an item by ID.

        Arguments:
            code: The generated access code to be retrieved.

        Returns:
            A GetResponse object after retrieving the item by id.

        Raises:
            DatabaseError: If there's an error during the retrieval operation.
            NotFoundError: If the item is not found.
        """
        try:
            # Get the record from the database
            record = await self._getitem(session=self.session, code=code)
            # Convert the record to a GET schema model
            return GetResponse.model_validate(record, from_attributes=True)
        except NotFoundError as e:
            message = f"Record with code {code} not found"
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "REDIS DB Error while retrieving item from Cache"
            logger.exception(message)
            raise DatabaseError(message) from e
