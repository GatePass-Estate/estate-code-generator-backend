import json
import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import UUID4

from app.core.exceptions import DatabaseError, NotFoundError
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    ListResponse,
    Receiver,
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
            NotFoundError: If item is not found or expired.
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
                        raise NotFoundError("Invalid code!")
                else:
                    raise Exception("Expiry timestamp missing in cached data")
                result["is_expired"] = False
                return result
            else:
                raise NotFoundError("Invalid code!")
        except NotFoundError:
            raise NotFoundError("Invalid code!")
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

    async def _delete_item(
        self,
        session: redis.Redis,
        code: str,
    ) -> bool:
        """
        Delete an item from the cache by its code.

        Args:
            session (redis.Redis): The redis session.
            code (str): The generated access code to be deleted.

        Returns:
            bool: True if the item was deleted, False if it didn't exist.

        Raises:
            HTTPException: If there's an error during the delete operation.
        """
        try:
            result = await session.delete(code)
            return result > 0
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _verify_item_exists(self, code: str) -> None:
        """
        Verify that an item exists in the cache (including expired items).

        Arguments:
            code (str): The generated access code to verify.

        Raises:
            NotFoundError: If the item is not found.
            DatabaseError: If there's an error during verification.
        """
        try:
            # Check if key exists in Redis without retrieving full data
            exists = await self.session.exists(code)
            if not exists:
                message = f"Record with code {code} not found"
                logger.warning(message)
                raise NotFoundError(message)

        except NotFoundError:
            raise
        except Exception as e:
            message = f"Error verifying item existence for code {code}"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def _verify_item_deleted(self, code: str) -> None:
        """
        Verify that an item has been successfully deleted from the cache.

        Arguments:
            code (str): The generated access code to verify deletion.

        Raises:
            DatabaseError: If the item still exists after deletion attempt.
        """
        try:
            # Check if key still exists after deletion
            still_exists = await self.session.exists(code)
            if still_exists:
                message = (
                    f"Record with code {code} "
                    "still exists after deletion attempt"
                )
                logger.error(message)
                raise DatabaseError(message)

        except DatabaseError:
            raise
        except Exception as e:
            message = f"Error verifying item deletion for code {code}"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def _get_all_items(
        self,
        user_id: UUID4,
        estate_id: UUID4,
    ) -> ListResponse:
        """
        Get all items from the cache, filtered by user_id.

        Args:
            user_id (str): Filter items by user_id provided.
            estate_id (str): Filter items by estate_id provided.

        Returns:
            ListResponse: List of cached items.

        Raises:
            HTTPException: If there's an error during the retrieval operation.
        """
        try:
            # Get all keys from Redis
            keys = await self.session.keys("*")
            items = []

            for key in keys:
                try:
                    data = await self.session.get(key)
                    if data:
                        result = json.loads(data)

                        # Check if entry is expired
                        valid_until = result.get("valid_until")
                        if valid_until:
                            valid_until_dt = datetime.strptime(
                                valid_until, "%Y-%m-%d %H:%M:%S.%f%z"
                            )
                            now = datetime.now(timezone.utc)

                            if now > valid_until_dt:
                                continue

                        # Filter by user_id if provided
                        if result.get("user_id") != str(user_id) or result.get(
                            "estate_id"
                        ) != str(estate_id):
                            continue

                        result["is_expired"] = False
                        result["receiver"] = Receiver.VISITOR
                        items.append(GetResponse.model_validate(result))

                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        f"Skipping invalid JSON entry for key {key}: {e}"
                    )
                    continue
            return ListResponse(
                items=items,
            )
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
            record["receiver"] = Receiver.VISITOR
            return GetResponse.model_validate(record, from_attributes=True)
        except NotFoundError as e:
            message = f"Record with code {code} not found"
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "REDIS DB Error while retrieving item from Cache"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def delete(self, code: str) -> bool:
        """
        Delete an item from the cache by its code.

        Arguments:
            code (str): The generated access code to be deleted.

        Returns:
            bool: True if the item was deleted successfully.

        Raises:
            DatabaseError: If there's an error during the delete operation.
            NotFoundError: If the item is not found.
        """
        try:
            # Check if item exists before deletion
            await self._verify_item_exists(code)

            # Perform deletion
            deleted = await self._delete_item(session=self.session, code=code)
            if not deleted:
                message = f"Failed to delete record with code {code}"
                logger.error(message)
                raise DatabaseError(message)

            # Final verification - ensure item was actually deleted
            await self._verify_item_deleted(code)

            return deleted

        except NotFoundError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            message = f"Unexpected error while deleting item with code {code}"
            logger.exception(message)
            raise DatabaseError(message) from e
