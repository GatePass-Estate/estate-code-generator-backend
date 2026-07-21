import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pydantic import UUID4

from app.core.config import settings
from app.core.exceptions import DatabaseError, NotFoundError, ScheduleError
from app.libs.auth import get_user_details
from app.libs.hash_gen import generate_unique_code
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.code_service import (
    CreateRequestResident,
    CreateRequestVisitor,
    CreateResponse,
    ExtendResponse,
    FreezeResponse,
    GetResponseResident,
    GetResponseVisitor,
    ListResponse,
    Receiver,
)

logger = logging.getLogger(__name__)


class CodeServiceRepository:
    """Orchestrates access code operations across cache and database services."""

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

    def _is_upcoming_visitor_code(self, item: dict, now: datetime) -> bool:
        """Return True when the code's validity period has not started yet."""
        period = item.get("validity_period") or {}
        start = period.get("start")
        if not start:
            return False
        start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S.%f%z")
        return now < start_dt

    def _is_visitor_code_expired(
        self, record: dict, now: datetime | None = None
    ) -> bool:
        """Return True when the visitor code is past its total validity end."""
        if now is None:
            now = datetime.now(timezone.utc)
        period = record.get("validity_period") or {}
        end = period.get("end") or record.get("valid_until")
        if not end:
            return False
        end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S.%f%z")
        return now > end_dt

    async def _resolve_resident_full_name(self, user_id: str | None) -> str:
        """
        Resolve a resident's full name for denormalized log storage.

        The name is stored on the log row at write time so history reads avoid
        an extra lookup or join. A lookup failure must not block validation, so
        this returns an empty string on any error.
        """
        if not user_id:
            return ""
        try:
            user = await get_user_details(self.ahttp_client, str(user_id))
        except Exception:
            logger.exception(
                "Failed to resolve resident name for user %s", user_id
            )
            return ""
        return (
            f"{user.get('first_name', '') or ''} "
            f"{user.get('last_name', '') or ''}"
        ).strip()

    async def _resolve_household_name(self, user_id: str | None) -> str | None:
        """Resolve the household display name for a resident user."""
        if not user_id:
            return None
        try:
            user = await get_user_details(self.ahttp_client, str(user_id))
        except Exception:
            logger.exception(
                "Failed to resolve household name for user %s", user_id
            )
            return None

        household_id = user.get("household_id")
        if not household_id:
            return None

        try:
            url = (
                f"{settings.DB_SERVICE_URL}api/v1/userprofile"
                f"/household/{household_id}"
            )
            household = await self.ahttp_client.async_get(url)
        except Exception:
            logger.exception(
                "Failed to fetch household %s for user %s",
                household_id,
                user_id,
            )
            return None

        return household.get("name") if household else None

    async def _soft_delete_previous_resident_codes(
        self,
        ahttp_client: AsyncHttpHandler,
        *,
        user_id: str,
        estate_id: str,
        keep_id: str,
    ) -> None:
        """
        Soft-delete active access codes for this resident except ``keep_id``.

        Called after a new code row is persisted so only one active code
        remains. Failures on individual deletes are logged and do not roll back
        the new code.
        """
        search_url = (
            f"{settings.DB_SERVICE_URL}api/v1/codeservice/accesscode/search"
        )
        params = {
            "user_id": user_id,
            "estate_id": estate_id,
            "page": 1,
            "limit": 50,
        }
        try:
            existing = await ahttp_client.async_get(search_url, params=params)
        except NotFoundError:
            return
        except Exception as exc:
            logger.warning(
                "Could not search prior access codes for soft delete "
                "user_id=%s estate_id=%s: %s",
                user_id,
                estate_id,
                exc,
            )
            return

        for item in existing.get("items") or []:
            old_id = item.get("id")
            if not old_id or str(old_id) == str(keep_id):
                continue
            delete_url = (
                f"{settings.DB_SERVICE_URL}"
                f"api/v1/codeservice/accesscode/{old_id}"
            )
            try:
                await ahttp_client.async_delete(delete_url)
                logger.info(
                    "Soft-deleted prior resident access code id=%s", old_id
                )
            except Exception as exc:
                logger.warning(
                    "Failed to soft-delete prior access code id=%s: %s",
                    old_id,
                    exc,
                )

    async def _getitem(
        self,
        ahttp_client: AsyncHttpHandler,
        **kwargs,
    ) -> dict:
        """
        Look up an access code in cache (visitor) or database (resident).

        Visitor codes are validated by cache_service, including total validity
        period, daily validity window, and freeze checks. Resident codes are
        checked for expiry only and return ``is_valid=True`` when active.

        Arguments:
            ahttp_client: HTTP client for downstream services.
            code: Access code to resolve.

        Returns:
            Raw record dict including ``receiver`` and validity fields.

        Raises:
            NotFoundError: If the code is missing or invalid.
            Exception: On unexpected downstream failures.
        """
        code = kwargs.get("code", None)

        try:
            # 1. First try to check it as a visitor's code
            url = (
                f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                f"/cachehandler/{code}"
            )
            response = await ahttp_client.async_get(url)
            if not response:
                logger.error("Visitor's code not found in cache!")
                raise NotFoundError("Invalid code!")
            response["receiver"] = Receiver.VISITOR
            return response
        except NotFoundError:
            # 2. If not found, try to check it as a resident's code
            url = (
                f"{settings.DB_SERVICE_URL}api/v1/codeservice"
                f"/accesscode/search"
            )
            params = {"hashed_code": code}
            response = await ahttp_client.async_get(url, params=params)
            if not response.get("items"):
                raise NotFoundError("Invalid code!")

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
                    raise NotFoundError("Invalid code!")
            else:
                raise Exception("Expiry timestamp missing in cached data!")
            resident_data["is_expired"] = False
            resident_data["is_valid"] = True
            resident_data["receiver"] = Receiver.RESIDENT
            return resident_data
        except Exception as e:
            logger.error(e)
            raise Exception(e) from e

    async def _get_items_by_user(
        self, **kwargs
    ) -> ListResponse | GetResponseResident:
        """
        Get all items linked to a given user ID.

        Arguments:
            user_id: The user ID to be retrieved for.
            recevier: The status of the code owner (visitor and resident)
            user_details: The details of the user making the request.

        Returns:
            A List response model containing reference to the retrieved items
            if the recever is 'visitor', or a single item if the receiver is
            'resident'.

        Raises:
            HTTPException: If there is an internal server error or retrieved
                item is expired for a resident.
            NotFoundError: If item is not found or expired.
        """

        user_id = kwargs.get("user_id", None)
        receiver = kwargs.get("receiver", None)
        user_details = kwargs.get("user_details", None)
        upcoming = kwargs.get("upcoming", False)

        try:
            if receiver == Receiver.VISITOR:
                url = (
                    f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                    f"/cachehandler/all/{user_id}"
                )
                params = {"estate_id": user_details.get("estate_id")}
                response = await self.ahttp_client.async_get(url, params)
                if upcoming:
                    now = datetime.now(timezone.utc)
                    response["items"] = [
                        item
                        for item in response.get("items", [])
                        if self._is_upcoming_visitor_code(item, now)
                    ]
                return response
            elif receiver == Receiver.RESIDENT:
                url = (
                    f"{settings.DB_SERVICE_URL}api/v1/codeservice"
                    f"/accesscode/search"
                )
                params = {
                    "user_id": user_id,
                    "estate_id": user_details.get("estate_id"),
                }
                response = await self.ahttp_client.async_get(
                    url, params=params
                )
                if not response.get("items"):
                    raise NotFoundError(f"No code found for user {user_id}!")

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
                        raise NotFoundError("Code has expired!")
                else:
                    raise Exception("Expiry timestamp missing in cached data")
                resident_data["is_expired"] = False
                resident_data["is_valid"] = True
                resident_data["receiver"] = Receiver.RESIDENT
                return resident_data
        except NotFoundError as e:
            logger.error(e)
            raise NotFoundError(e) from e
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=str(e))

    async def _setitem(
        self,
        ahttp_client: AsyncHttpHandler,
        request: CreateRequestVisitor | CreateRequestResident,
        receiver: Receiver,
    ) -> dict:
        """
        Persist a new access code for a visitor or resident.

        Visitor codes are sent to cache_service with optional
        ``validity_period`` and ``validity_window``. Resident codes are
        stored in db-service with a ``RESIDENT_CODE_EXPIRY_DAYS`` expiry.

        Args:
            ahttp_client: HTTP client for downstream services.
            request: Visitor or resident create payload.
            receiver: Whether the code is for a visitor or resident.

        Returns:
            Dict with ``hashed_code`` and ``valid_until``.

        Raises:
            HTTPException: On downstream persistence failures.
        """
        try:
            if receiver == Receiver.VISITOR:
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
                    receiver=receiver,
                    validity_period=visit_data.get("validity_period"),
                )
                visit_data["hashed_code"] = code
                data = {"hashed_code": code, "visit_data": visit_data}
                response = await ahttp_client.async_post(
                    cache_url, json_data=data
                )
                return response
            elif receiver == Receiver.RESIDENT:
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
                    receiver=receiver,
                )
                resident_data["hashed_code"] = code
                valid_until = datetime.now(timezone.utc) + timedelta(
                    days=settings.RESIDENT_CODE_EXPIRY_DAYS
                )
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
                    raise Exception("Failed to generate code for resident!")
                new_id = persist_code.get("id") if persist_code else None
                if new_id:
                    await self._soft_delete_previous_resident_codes(
                        self.ahttp_client,
                        user_id=str(resident_data.get("user_id")),
                        estate_id=str(resident_data.get("estate_id")),
                        keep_id=str(new_id),
                    )
                response = {
                    "hashed_code": code,
                    "valid_until": valid_until,
                }
                return response
        except ScheduleError:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def _delete(self, **kwargs) -> bool:
        """
        Delete an item by its associated code in the cache.

        Arguments:
            code: The generated access code to be deleted.
            user_details: The user details of the user trying to delete the
                record.

        Returns:
            A boolean indicating whether the item was deleted successfully.
            Returns False when the code is expired or is a resident code.

        Raises:
            NotFoundError: If the code is missing or the requester is not the
                owner.
            HTTPException: If there is an internal server error
        """

        code = kwargs.get("code", None)
        user_details = kwargs.get("user_details", None)

        try:
            raw_url = (
                f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                f"/cachehandler/{code}/raw"
            )
            try:
                record = await self.ahttp_client.async_get(raw_url)
            except NotFoundError:
                record = None

            if record:
                if self._is_visitor_code_expired(record):
                    logger.info(
                        "Skipping delete for expired visitor code %s", code
                    )
                    return False

                if str(record.get("user_id")) != user_details.get("id"):
                    message = (
                        "User is not authorized to delete this resource "
                        "due to user_id mismatch!"
                    )
                    logger.exception(message)
                    raise NotFoundError(f"Invalid code: {code}!")

                cache_url = (
                    f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
                    f"/cachehandler/{code}"
                )
                return await self.ahttp_client.async_delete(cache_url)

            url = (
                f"{settings.DB_SERVICE_URL}api/v1/codeservice"
                f"/accesscode/search"
            )
            params = {"hashed_code": code}
            response = await self.ahttp_client.async_get(url, params=params)
            if response.get("items"):
                logger.info(
                    "Resident's code can't be deleted from this endpoint!"
                )
                return False

            raise NotFoundError(f"Invalid code: {code}!")
        except NotFoundError:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def _update_resident_code(
        self,
        ahttp_client: AsyncHttpHandler,
        **kwargs,
    ) -> dict:
        """
        Update a resident's access code in the database.

        Arguments:
            ahttp_client: The HttpClient session.
            user_id: The user ID of the resident whose code needs to be updated
            user_details: The details of the user making the request.

        Returns:
            dict: Returns the response dict containing the new code details.

        Raises:
            HTTPException: If there is an unexpected error during the update.
            NotFoundError: If the resident code is not found.
        """
        user_id = kwargs.get("user_id", None)
        user_details = kwargs.get("user_details", None)

        try:
            # First, check if the resident code exists
            db_url = (
                f"{settings.DB_SERVICE_URL}api/v1/codeservice"
                f"/accesscode/search"
            )
            params = {
                "user_id": user_id,
                "estate_id": user_details.get("estate_id"),
            }
            existing_response = await ahttp_client.async_get(
                db_url, params=params
            )

            if not existing_response.get("items"):
                raise NotFoundError(f"No code found for resident {user_id}!")

            # Generate new code
            now = datetime.now(timezone.utc)
            new_code = generate_unique_code(
                user_id=user_id,
                estate_id=user_details.get("estate_id"),
                date=now.strftime("%Y-%m-%d"),
                hour=now.strftime("%H"),
                receiver=Receiver.RESIDENT,
            )

            # Calculate new expiry date
            valid_until = datetime.now(timezone.utc) + timedelta(
                days=settings.RESIDENT_CODE_EXPIRY_DAYS
            )
            valid_until = self._format_datetime(valid_until)

            # Update the existing record
            id = existing_response.get("items")[0]["id"]
            update_url = (
                f"{settings.DB_SERVICE_URL}api/v1/codeservice/accesscode/{id}"
            )
            update_data = {
                "user_id": str(user_id),
                "estate_id": user_details.get("estate_id"),
                "hashed_code": new_code,
                "valid_until": valid_until,
            }

            try:
                update_response = await ahttp_client.async_patch(
                    update_url, json_data=update_data
                )
                logger.info("Resident code updated in DB: %s", update_response)
            except Exception as update_exception:
                logger.error(
                    "Error updating resident code %s in DB: %s",
                    new_code,
                    update_exception,
                )
                raise Exception("Failed to update code for resident!")

            response = {
                "hashed_code": new_code,
                "valid_until": valid_until,
            }
            return response

        except NotFoundError:
            raise NotFoundError(f"No code found for resident {user_id}!")
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=str(e))

    async def create(
        self,
        request: CreateRequestVisitor | CreateRequestResident,
        receiver: Receiver,
        user_details: dict | None = None,
    ) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for generating a new access code.
            receiver: The status of the code owner (visitor of resident).
            user_details: The user details of the user trying to generate the
                code.

        Returns:
            The CreateResponse object after creating the item in the table.

        Raises:
            ScheduleError: If the visitor validity period exceeds 2 weeks.
            DatabaseError: If there's an error during the database operation.
        """
        if str(request.estate_id) != user_details.get("estate_id") or str(
            request.user_id
        ) != user_details.get("id"):
            message = (
                "User is not authorized to generate code for this estate/user!"
            )
            logger.exception(message)
            raise Exception("Invalid estate or user!")

        try:
            # Create the record in the database
            response = await self._setitem(
                ahttp_client=self.ahttp_client,
                request=request,
                receiver=receiver,
            )
            created_record = CreateResponse.model_validate(response)
            return created_record
        except ScheduleError:
            raise
        except DatabaseError as e:
            message = "Database error in creating the access code"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(
        self, code: str, user_details: dict | None = None
    ) -> GetResponseVisitor | GetResponseResident:
        """
        Validate an access code and persist a visitor or resident log entry.

        Visitor validation uses cache_service lifecycle checks. Resident
        validation checks expiry only. The caller's estate must match the
        code's estate. Log rows are written with denormalized resident names
        (``full_name`` on resident logs, ``resident_fullname`` on visitor
        logs) resolved at validation time.
        """
        try:
            # Get the record from the database
            record = await self._getitem(
                ahttp_client=self.ahttp_client, code=code
            )

            if record.get("estate_id") != user_details.get("estate_id"):
                message = (
                    "User is not authorized to access this resource "
                    "due to estate_id mismatch!"
                )
                logger.exception(message)
                raise NotFoundError(f"Invalid code: {code}!")

            record["household_name"] = await self._resolve_household_name(
                record.get("user_id")
            )

            if record and (record.get("receiver") == Receiver.VISITOR):
                # Record was retrieved from the cache. Now, persist to DB.
                full_name = await self._resolve_resident_full_name(
                    record.get("user_id")
                )
                visitlog_data = {
                    "user_id": record.get("user_id"),
                    "estate_id": record.get("estate_id"),
                    "resident_fullname": full_name,
                    "visitor_fullname": record.get("visitor_fullname"),
                    "relationship_with_resident": record.get(
                        "relationship_with_resident"
                    ),
                    "gender": record.get("gender"),
                    "hashed_code": record.get("hashed_code"),
                    "security_id": user_details.get("id"),
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
                    raise DatabaseError(
                        "Error persisting visitor's record to DB"
                    ) from persist_exception
                # Convert the record to a GET schema model
                return GetResponseVisitor.model_validate(
                    record, from_attributes=True
                )
            elif record and (record.get("receiver") == Receiver.RESIDENT):
                # Record was retrieved from access code. Now, persist to DB.
                full_name = await self._resolve_resident_full_name(
                    record.get("user_id")
                )
                residentlog_data = {
                    "user_id": record.get("user_id"),
                    "estate_id": record.get("estate_id"),
                    "full_name": full_name,
                    "hashed_code": record.get("hashed_code"),
                    "security_id": user_details.get("id"),
                    "access_time": record.get("visit_time"),
                }
                try:
                    db_url = (
                        f"{settings.DB_SERVICE_URL}api/v1/"
                        "codeservice/residentlog"
                    )
                    persist_response = await self.ahttp_client.async_post(
                        db_url, json_data=residentlog_data
                    )
                    logger.info("Record persisted to DB: %s", persist_response)
                except Exception as persist_exception:
                    logger.error(
                        "Error persisting record with code %s to DB: %s",
                        code,
                        persist_exception,
                    )
                    raise DatabaseError(
                        "Error persisting resident's record to DB"
                    ) from persist_exception
                return GetResponseResident.model_validate(
                    record, from_attributes=True
                )
        except NotFoundError as e:
            message = f"Invalid code: {code}!"
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = f"Database error in getting a record with code {code}"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = f"Error in getting a record with code {code}"
            logger.exception(message)
            raise Exception(message) from e

    async def _authorize_visitor_code_owner(
        self, code: str, user_details: dict
    ) -> dict:
        """
        Verify that the requester owns a visitor access code.

        Loads the raw cached record (without validity filtering) and compares
        ``user_id`` to the authenticated resident.

        Raises:
            NotFoundError: If the code is missing or the requester is not the
                owner.
        """
        raw_url = (
            f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
            f"/cachehandler/{code}/raw"
        )
        try:
            record = await self.ahttp_client.async_get(raw_url)
        except NotFoundError:
            logger.warning(
                "Visitor code owner auth failed code=%s requester_id=%s "
                "reason=not_found",
                code,
                user_details.get("id"),
            )
            raise NotFoundError(f"Invalid code: {code}!")
        except Exception as exc:
            logger.error(
                "Visitor code owner auth failed code=%s requester_id=%s "
                "error=%s",
                code,
                user_details.get("id"),
                exc,
            )
            raise NotFoundError(f"Invalid code: {code}!") from exc

        if str(record.get("user_id")) != user_details.get("id"):
            logger.warning(
                "Visitor code owner auth failed code=%s requester_id=%s "
                "owner_id=%s reason=user_id_mismatch",
                code,
                user_details.get("id"),
                record.get("user_id"),
            )
            raise NotFoundError(f"Invalid code: {code}!")
        logger.info(
            "Visitor code owner authorized code=%s requester_id=%s",
            code,
            user_details.get("id"),
        )
        return record

    async def extend_code(
        self, code: str, user_details: dict | None = None
    ) -> ExtendResponse:
        """
        Extend a visitor code once by adding one hour to the period end.

        Requires the requester to own the code. Delegates persistence to
        cache_service, which updates ``validity_period.end``, ``valid_until``,
        and Redis TTL.
        """
        await self._authorize_visitor_code_owner(code, user_details)
        extend_url = (
            f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
            f"/cachehandler/{code}/extend"
        )
        response = await self.ahttp_client.async_patch(extend_url)
        result = ExtendResponse.model_validate(response)
        logger.info(
            "Visitor code extend requested code=%s requester_id=%s "
            "success=%s valid_until=%s extended=%s",
            code,
            user_details.get("id"),
            result.success,
            result.valid_until,
            result.extended,
        )
        return result

    async def toggle_freeze_code(
        self, code: str, user_details: dict | None = None
    ) -> FreezeResponse:
        """
        Toggle freeze/pause on a visitor access code.

        Requires the requester to own the code. Freeze does not modify the
        total validity period or daily validity window.
        """
        await self._authorize_visitor_code_owner(code, user_details)
        freeze_url = (
            f"{settings.CACHE_SERVICE_URL}api/v1/cacheservice"
            f"/cachehandler/{code}/freeze"
        )
        response = await self.ahttp_client.async_patch(freeze_url)
        result = FreezeResponse.model_validate(response)
        logger.info(
            "Visitor code freeze toggled code=%s requester_id=%s "
            "frozen=%s is_valid=%s",
            code,
            user_details.get("id"),
            result.frozen,
            result.is_valid,
        )
        return result

    async def update_resident_code(
        self, user_id: UUID4, user_details: dict | None = None
    ) -> CreateResponse:
        """
        Update a resident's access code.

        Arguments:
            user_id: The ID of the resident whose code needs to be updated.
            user_details: The user details of the user making the request.

        Returns:
            The CreateResponse object after updating the resident's code.

        Raises:
            DatabaseError: If there's an error during the database operation.
            NotFoundError: If the resident code is not found.
        """
        # Validate that the user is authorized to update this resident's code
        if str(user_id) != user_details.get("id"):
            message = (
                "User is not authorized to update code for this resident!"
            )
            logger.exception(message)
            raise Exception("Invalid user!")

        try:
            # Update the resident's code
            response = await self._update_resident_code(
                ahttp_client=self.ahttp_client,
                user_id=user_id,
                user_details=user_details,
            )
            updated_record = CreateResponse.model_validate(response)
            return updated_record
        except NotFoundError as e:
            message = f"Resident code not found for user {user_id}"
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in updating the resident's access code"
            logger.exception(message)
            raise DatabaseError(message) from e
