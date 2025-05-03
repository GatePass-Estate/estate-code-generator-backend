import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import DatabaseError, NotFoundError
from app.libs.hash_gen import generate_unique_code
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.code_service import (
    CreateRequestResident,
    CreateRequestVisitor,
    CreateResponse,
    GetResponseResident,
    GetResponseVisitor,
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
            session: The HttpClient session.
        """
        self.ahttp_client: AsyncHttpHandler = ahttp_client

    def _format_datetime(self, dt: datetime) -> str:
        ms = int(dt.microsecond / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d}+0000"

    async def _getitem(
        self,
        ahttp_client: AsyncHttpHandler,
        **kwargs,
    ) -> dict:
        """
        Get an item from the table by its ID.

        Arguments:
            session: The HttpClient session.
            code: The generated access code to be retrieved.
            receiver: The status of the code owner (visitor or resident).

        Returns:
            Returns an instance of orm_model if the requested item is found.

        Raises:
            HTTPException: If item is not found, is expired, timestamp is
                missing, or unexpected error occured during retrieval.
        """
        code = kwargs.get("code", None)
        receiver = kwargs.get("receiver", None)

        # TODO: Account for receiver=resident and call from db-service instead
        try:
            if receiver == "visitor":
                url = (
                    f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                    f"/cachehandler/{code}"
                )
                response = await ahttp_client.async_get(url)
                return response
            else:
                url = (
                    f"{settings.DB_SERVICE_URL}api/v1/codeservice"
                    f"/accesscode/search"
                )
                params = {"hashed_code": code}
                response = await ahttp_client.async_get(url, params=params)
                if not response.get("items"):
                    raise Exception("Error retrieving record from Database!")

                response = response.get("items")[0]
                valid_until = response.get("valid_until")
                resident_data = {
                    "user_id": response.get("user_id"),
                    "estate_id": response.get("estate_id"),
                    "hashed_code": response.get("hashed_code"),
                    "valid_until": valid_until,
                    "visit_time": datetime.now(timezone.utc).isoformat(),
                }
                if valid_until:
                    valid_until = datetime.fromisoformat(
                        valid_until.replace("Z", "+00:00")
                    )
                    now = datetime.now(timezone.utc)

                    if now > valid_until:
                        raise HTTPException(
                            status_code=400, detail="Code has expired"
                        )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Expiry timestamp missing in cached data",
                    )
                resident_data["is_expired"] = False
                return resident_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _setitem(
        self,
        ahttp_client: AsyncHttpHandler,
        request: CreateRequestVisitor | CreateRequestResident,
        receiver: str,
    ) -> dict:
        """
        Create a new record in the database.

        Args:
            session (AsyncHttpHandler): The HttpClient session.
            request (CreateRequestVisito | CreateRequestResident): The record
                to be created/inserted in the database/redis cache.
            recevier (str): The status of the code owner (visitor or resident).

        Returns:
            dict: Returns the response dict containing the details of the
                operation.

        Raises:
            HTTPException: If there is an unexpected error occured during
                retrieval.
        """
        try:
            if receiver == "visitor":
                cache_url = (
                    f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                    f"/cachehandler"
                )

                visit_data = request.model_dump()
                now = datetime.now(timezone.utc)
                code = generate_unique_code(
                    user_id=visit_data.get("user_id"),
                    estate_id=visit_data.get("estate_id"),
                    visitor_fullname=visit_data.get("visitor_fullname"),
                    relationship_with_resident=visit_data.get(
                        "relationship_with_resident"
                    ),
                    date=now.strftime("%Y-%m-%d"),
                    hour=now.strftime("%H"),
                    receiver="visitor",
                )
                visit_data["hashed_code"] = code
                data = {"hashed_code": code, "visit_data": visit_data}
                response = await ahttp_client.async_post(
                    cache_url, json_data=data
                )
                return response
            else:
                db_url = (
                    f"{settings.DB_SERVICE_URL}api/v1/codeservice/accesscode"
                )

                resident_data = request.model_dump()
                now = datetime.now(timezone.utc)
                code = generate_unique_code(
                    user_id=resident_data.get("user_id"),
                    estate_id=resident_data.get("estate_id"),
                    date=now.strftime("%Y-%m-%d"),
                    hour=now.strftime("%H"),
                    receiver="resident",
                )
                resident_data["hashed_code"] = code
                valid_until = datetime.now(timezone.utc) + timedelta(days=120)
                valid_until = self._format_datetime(valid_until)
                resident_data["valid_until"] = valid_until
                try:
                    persist_code = await self.ahttp_client.async_post(
                        db_url, json_data=resident_data
                    )
                    logger.info("Record persisted to DB: %s", persist_code)
                except Exception as persist_exception:
                    logger.error(
                        "Error persisting record with code %s to DB: %s",
                        code,
                        persist_exception,
                    )
                    raise Exception("Failed to generate code for resdient!")
                response = {
                    "hashed_code": code,
                    "valid_until": valid_until,
                }
                return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def create(
        self,
        request: CreateRequestVisitor | CreateRequestResident,
        receiver: str,
    ) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for generating a new access code.
            receiver: The status of the code owner (visitor of resident).

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
            message = "Database error in creating the access code"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(
        self, code: str, receiver: str
    ) -> GetResponseVisitor | GetResponseResident:
        """
        Get an item by code. If the recevier is a visitor, the retrieved record
        is persisted to the DB for permanent logging.

        Arguments:
            code: The generated access code to be validated.
            receiver: The status of the code owner (visitor or resident).

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
            if record and (receiver == "visitor"):
                # Record was retrieved from the cache. Now, persist to DB.
                visitlog_data = {
                    "user_id": record.get("user_id"),
                    "visitor_fullname": record.get("visitor_fullname"),
                    "relationship_with_resident": record.get(
                        "relationship_with_resident"
                    ),
                    "hashed_code": record.get("hashed_code"),
                    "security_id": "64b7d74d-bb97-45be-87c3-6c91243b69e8",
                    "visit_time": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    db_url = (
                        f"{settings.DB_SERVICE_URL}api/v1/"
                        "codeservice/visitorlog"
                    )
                    persist_response = await self.ahttp_client.async_post(
                        db_url, json_data=visitlog_data
                    )
                    logger.info("Record persisted to DB: %s", persist_response)
                except Exception as persist_exception:
                    logger.error(
                        "Error persisting record with code %s to DB: %s",
                        code,
                        persist_exception,
                    )
                # Convert the record to a GET schema model
                return GetResponseVisitor.model_validate(
                    record, from_attributes=True
                )
            else:
                return GetResponseResident.model_validate(
                    record, from_attributes=True
                )
        except NotFoundError as e:
            message = f"Record with code {code} not found"
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = f"Database error in getting a record with code {code}"
            logger.exception(message)
            raise DatabaseError(message) from e
