import json
import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from fastapi import HTTPException
from pydantic import UUID4

from app.core.config import settings
from app.core.exceptions import DatabaseError, NotFoundError, ScheduleError
from app.libs.code_validity import evaluate_code_validity, parse_datetime
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    ExtendResponse,
    FreezeResponse,
    GetResponse,
    ListResponse,
    Receiver,
)

logger = logging.getLogger(__name__)


def _max_validity_period() -> timedelta:
    return timedelta(days=settings.VISITOR_CODE_MAX_VALIDITY_DAYS)


def _max_period_length() -> timedelta:
    return timedelta(days=settings.VISITOR_CODE_MAX_PERIOD_LENGTH_DAYS)


def _schedule_error_message() -> str:
    days = settings.VISITOR_CODE_MAX_VALIDITY_DAYS
    return (
        f"Validity period cannot be scheduled more than {days} days "
        "from the current time."
    )


class CacheHandlerRepository:
    """Redis repository for visitor access codes and their lifecycle state."""

    def __init__(self, session: redis.Redis) -> None:
        """
        Initialize the repository with a Redis session.

        Arguments:
            session: Async Redis client used for cache reads and writes.
        """
        self.session: redis.Redis = session

    def _format_datetime(self, dt: datetime) -> str:
        ms = int(dt.microsecond / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d}+0000"

    def _resolve_validity_period(
        self, visit_data: dict, now: datetime
    ) -> tuple[datetime, datetime]:
        """
        Resolve the total validity period for a new visitor code.

        Defaults to ``now`` through ``now + 1 hour`` when both bounds are
        omitted. Partial input fills missing bounds with those defaults.
        Callers must enforce the configured validity horizon after resolution.

        Raises:
            ScheduleError: If the resolved end is before the start.
        """
        raw_period = visit_data.get("validity_period") or {}
        if isinstance(raw_period, dict):
            vp_start = raw_period.get("start")
            vp_end = raw_period.get("end")
        else:
            vp_start = getattr(raw_period, "start", None)
            vp_end = getattr(raw_period, "end", None)

        if not vp_start and not vp_end:
            return now, now + timedelta(hours=1)

        period_start = parse_datetime(vp_start) if vp_start else now
        period_end = (
            parse_datetime(vp_end) if vp_end else now + timedelta(hours=1)
        )
        if period_start < now:
            raise ScheduleError("Validity period start cannot be in the past.")
        if period_end < period_start:
            raise ScheduleError(
                "Validity period end cannot be before the start."
            )
        return period_start, period_end

    def _enforce_validity_period_horizon(
        self,
        period_start: datetime,
        period_end: datetime,
        now: datetime,
    ) -> None:
        """
        Reject invalid validity period bounds.

        Ensures the period does not exceed the configured horizon from ``now``,
        that end is not equal to start, and that the span does not exceed the
        configured maximum length.

        Raises:
            ScheduleError: If any bound rule is violated.
        """

        horizon = now + _max_validity_period()
        if period_start > horizon:
            raise ScheduleError(_schedule_error_message())

        if period_end == period_start:
            raise ScheduleError(
                "Validity period end cannot be the same as the start."
            )

        max_span = _max_period_length()
        if period_end - period_start > max_span:
            days = settings.VISITOR_CODE_MAX_PERIOD_LENGTH_DAYS
            raise ScheduleError(
                f"Validity period cannot exceed {days} days from the start."
            )

    def _normalize_validity_window(self, visit_data: dict) -> dict:
        """Normalize daily validity window to ``{start, end}`` or null bounds."""
        raw_window = visit_data.get("validity_window") or {}
        if not isinstance(raw_window, dict):
            raw_window = raw_window.model_dump() if raw_window else {}
        if not raw_window.get("start") and not raw_window.get("end"):
            return {"start": None, "end": None}
        return {
            "start": raw_window.get("start"),
            "end": raw_window.get("end"),
        }

    async def _get_raw(
        self,
        session: redis.Redis,
        code: str,
    ) -> dict:
        """Load a cached visitor code without applying validity checks."""
        data = await session.get(code)
        if not data:
            raise NotFoundError("Invalid code!")
        return json.loads(data)

    async def _getitem(
        self,
        session: redis.Redis,
        **kwargs,
    ) -> dict:
        """
        Validate and return a visitor access code from Redis.

        Arguments:
            session: The Redis session.
            code: The generated access code to retrieve.

        Returns:
            Enriched cache record including computed ``is_valid`` flags.

        Raises:
            NotFoundError: If the code is missing or fails validity checks.
            HTTPException: If expiry metadata is missing or an unexpected
                error occurs.
        """
        code = kwargs.get("code", None)
        try:
            result = await self._get_raw(session, code)
            period_end = result.get("valid_until") or (
                (result.get("validity_period") or {}).get("end")
            )
            if not period_end:
                raise Exception("Expiry timestamp missing in cached data")

            enriched = evaluate_code_validity(result)
            if not enriched.get("is_valid"):
                logger.warning(
                    "Visitor code validation failed code=%s user_id=%s "
                    "expired=%s before_period_start=%s frozen=%s "
                    "outside_daily_window=%s",
                    code,
                    result.get("user_id"),
                    enriched.get("is_expired"),
                    enriched.get("is_before_period_start"),
                    enriched.get("is_frozen"),
                    enriched.get("is_outside_daily_window"),
                )
                raise NotFoundError("Invalid code!")
            logger.info(
                "Visitor code validated code=%s user_id=%s valid_until=%s",
                code,
                result.get("user_id"),
                result.get("valid_until"),
            )
            return enriched
        except NotFoundError:
            logger.warning(
                "Visitor code lookup failed code=%s reason=not_found_or_invalid",
                code,
            )
            raise NotFoundError("Invalid code!")
        except Exception as e:
            logger.exception("Visitor code lookup failed code=%s", code)
            raise HTTPException(status_code=500, detail=str(e))

    async def _setitem(
        self,
        session: redis.Redis,
        request: CreateRequest,
    ) -> dict:
        """
        Persist a new visitor access code to Redis.

        Sets lifecycle defaults (``extended=False``, ``frozen=False``),
        resolves ``validity_period`` and ``validity_window``, mirrors
        ``valid_until`` to ``validity_period.end``, and sets Redis TTL from
        the period end.

        The total validity period must not start or end beyond the configured
        maximum horizon (``VISITOR_CODE_MAX_VALIDITY_DAYS``).

        Args:
            session: The Redis session.
            request: Visitor code payload to cache.

        Returns:
            Dict with ``hashed_code`` and ``valid_until``.

        Raises:
            ScheduleError: If the validity period end is before the start,
                equal to the start, exceeds the configured maximum span, or
                either bound exceeds the configured horizon.
            HTTPException: If persistence fails unexpectedly.
        """
        try:
            code = request.hashed_code
            visit_data = request.visit_data.model_dump()
            now = datetime.now(timezone.utc)

            period_start, period_end = self._resolve_validity_period(
                visit_data, now
            )
            self._enforce_validity_period_horizon(
                period_start, period_end, now
            )
            visit_data["validity_period"] = {
                "start": self._format_datetime(period_start),
                "end": self._format_datetime(period_end),
            }
            visit_data["valid_until"] = visit_data["validity_period"]["end"]
            visit_data["extended"] = False
            visit_data["frozen"] = False
            visit_data["validity_window"] = self._normalize_validity_window(
                visit_data
            )

            redis_expire = max(1, int((period_end - now).total_seconds()))
            await session.set(code, json.dumps(visit_data), ex=redis_expire)
            logger.info(
                "Visitor code created code=%s user_id=%s estate_id=%s "
                "validity_period_start=%s validity_period_end=%s "
                "validity_window=%s redis_expire=%ss",
                code,
                visit_data.get("user_id"),
                visit_data.get("estate_id"),
                visit_data["validity_period"]["start"],
                visit_data["validity_period"]["end"],
                visit_data["validity_window"],
                redis_expire,
            )
            response = {
                "hashed_code": code,
                "valid_until": visit_data["valid_until"],
            }
            return response
        except ScheduleError:
            raise
        except Exception as e:
            logger.exception(
                "Visitor code create failed code=%s", request.hashed_code
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def _extend_item(
        self,
        session: redis.Redis,
        code: str,
    ) -> dict:
        """
        Extend a visitor code once by adding one hour to ``validity_period.end``.

        Leaves ``validity_period.start`` and ``validity_window`` unchanged,
        updates ``valid_until`` to match the new end, and refreshes Redis TTL.

        Returns ``success=False`` without mutation when the code was already
        extended.
        """
        try:
            result = await self._get_raw(session, code)
            now = datetime.now(timezone.utc)
            hashed_code = result.get("hashed_code", code)
            validity_period = result.get("validity_period") or {}
            valid_until = result.get("valid_until") or validity_period.get(
                "end", ""
            )

            if result.get("extended"):
                logger.warning(
                    "Extend rejected code=%s user_id=%s reason=already_extended "
                    "valid_until=%s",
                    hashed_code,
                    result.get("user_id"),
                    valid_until,
                )
                return {
                    "success": False,
                    "hashed_code": hashed_code,
                    "valid_until": valid_until,
                    "validity_period": validity_period,
                    "extended": True,
                    "message": "Code has already been extended",
                }

            current_end = parse_datetime(valid_until) if valid_until else now
            new_end = current_end + timedelta(hours=1)
            new_end_str = self._format_datetime(new_end)
            validity_period["end"] = new_end_str
            result["validity_period"] = validity_period
            result["valid_until"] = new_end_str
            result["extended"] = True

            redis_expire = max(1, int((new_end - now).total_seconds()))
            await session.set(code, json.dumps(result))
            await session.expire(code, redis_expire)
            logger.info(
                "Visitor code extended code=%s user_id=%s "
                "previous_valid_until=%s new_valid_until=%s "
                "extension=+1h_from_previous_end redis_expire=%ss",
                hashed_code,
                result.get("user_id"),
                valid_until,
                new_end_str,
                redis_expire,
            )

            return {
                "success": True,
                "hashed_code": hashed_code,
                "valid_until": new_end_str,
                "validity_period": validity_period,
                "extended": True,
                "message": None,
            }
        except NotFoundError:
            logger.warning("Extend failed code=%s reason=not_found", code)
            raise NotFoundError("Invalid code!")
        except Exception as e:
            logger.exception("Extend failed code=%s", code)
            raise HTTPException(status_code=500, detail=str(e))

    async def _toggle_freeze(
        self,
        session: redis.Redis,
        code: str,
    ) -> dict:
        """
        Toggle the ``frozen`` flag on a cached visitor code.

        Does not modify ``validity_period``, ``validity_window``, or Redis TTL.
        """
        try:
            result = await self._get_raw(session, code)
            previous_frozen = bool(result.get("frozen", False))
            result["frozen"] = not previous_frozen

            redis_ttl = await session.ttl(code)
            await session.set(code, json.dumps(result))
            if redis_ttl > 0:
                await session.expire(code, redis_ttl)

            enriched = evaluate_code_validity(result)
            logger.info(
                "Visitor code freeze toggled code=%s user_id=%s "
                "frozen=%s->%s is_valid=%s redis_ttl=%ss",
                result.get("hashed_code", code),
                result.get("user_id"),
                previous_frozen,
                result["frozen"],
                enriched.get("is_valid"),
                redis_ttl,
            )
            return {
                "hashed_code": result.get("hashed_code", code),
                "frozen": result["frozen"],
                "is_valid": enriched.get("is_valid", False),
            }
        except NotFoundError:
            logger.warning(
                "Freeze toggle failed code=%s reason=not_found", code
            )
            raise NotFoundError("Invalid code!")
        except Exception as e:
            logger.exception("Freeze toggle failed code=%s", code)
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
        List non-expired visitor codes for a resident and estate.

        Expired codes are omitted. Codes that are frozen, before their total
        period start, or outside the daily window are still returned with
        ``is_valid=False``.

        Args:
            user_id: Resident who issued the visitor codes.
            estate_id: Estate the codes belong to.

        Returns:
            ListResponse ordered by ``valid_until`` descending.

        Raises:
            HTTPException: If Redis enumeration fails.
        """
        try:
            keys = await self.session.keys("*")
            items = []
            now = datetime.now(timezone.utc)

            for key in keys:
                try:
                    data = await self.session.get(key)
                    if data:
                        result = json.loads(data)
                        enriched = evaluate_code_validity(result, now)

                        if enriched.get("is_expired"):
                            continue

                        if result.get("user_id") != str(user_id) or result.get(
                            "estate_id"
                        ) != str(estate_id):
                            continue

                        if "validity_period" not in enriched:
                            end = enriched.get("valid_until")
                            enriched["validity_period"] = {
                                "start": None,
                                "end": end,
                            }
                        if "validity_window" not in enriched:
                            enriched["validity_window"] = {
                                "start": None,
                                "end": None,
                            }
                        if "extended" not in enriched:
                            enriched["extended"] = False
                        if "frozen" not in enriched:
                            enriched["frozen"] = False

                        enriched["receiver"] = Receiver.VISITOR
                        items.append(GetResponse.model_validate(enriched))

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
        Create and cache a visitor access code.

        Arguments:
            request: Visitor code payload including optional validity bounds.

        Returns:
            CreateResponse with ``hashed_code`` and ``valid_until``.

        Raises:
            ScheduleError: If the requested validity period exceeds the
                configured horizon.
            DatabaseError: If Redis persistence fails.
        """
        try:
            response = await self._setitem(
                session=self.session, request=request
            )
            created_record = CreateResponse.model_validate(response)
            return created_record
        except ScheduleError:
            raise
        except DatabaseError as e:
            message = "REDIS DB Error while inserting item into Cache"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, code: str) -> GetResponse:
        """
        Validate and return a visitor access code.

        Arguments:
            code: The generated access code to retrieve.

        Returns:
            GetResponse including lifecycle and computed validity fields.

        Raises:
            NotFoundError: If the code is missing or invalid.
            DatabaseError: If Redis retrieval fails unexpectedly.
        """
        try:
            record = await self._getitem(session=self.session, code=code)
            if "validity_period" not in record:
                record["validity_period"] = {
                    "start": None,
                    "end": record.get("valid_until"),
                }
            if "validity_window" not in record:
                record["validity_window"] = {"start": None, "end": None}
            if "extended" not in record:
                record["extended"] = False
            if "frozen" not in record:
                record["frozen"] = False
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

    async def get_raw(self, code: str) -> dict:
        """
        Return a cached visitor record without validity filtering.

        Used for internal ownership checks before extend/freeze operations.
        """
        try:
            record = await self._get_raw(self.session, code)
            logger.info(
                "Raw visitor code fetched code=%s user_id=%s frozen=%s "
                "extended=%s",
                code,
                record.get("user_id"),
                record.get("frozen"),
                record.get("extended"),
            )
            return record
        except NotFoundError as e:
            logger.warning("Raw visitor code fetch failed code=%s", code)
            raise NotFoundError(f"Record with code {code} not found") from e

    async def extend(self, code: str) -> ExtendResponse:
        """
        Extend a visitor code once by adding one hour to the current period end.

        Raises:
            NotFoundError: If the code does not exist in Redis.
            HTTPException: On unexpected persistence errors.
        """
        try:
            response = await self._extend_item(self.session, code)
            result = ExtendResponse.model_validate(response)
            logger.info(
                "Extend completed code=%s success=%s valid_until=%s",
                code,
                result.success,
                result.valid_until,
            )
            return result
        except NotFoundError:
            raise
        except Exception as e:
            logger.exception("Extend repository call failed code=%s", code)
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def toggle_freeze(self, code: str) -> FreezeResponse:
        """
        Toggle the frozen/paused state of a visitor access code.

        Raises:
            NotFoundError: If the code does not exist in Redis.
            HTTPException: On unexpected persistence errors.
        """
        try:
            response = await self._toggle_freeze(self.session, code)
            result = FreezeResponse.model_validate(response)
            logger.info(
                "Freeze toggle completed code=%s frozen=%s is_valid=%s",
                code,
                result.frozen,
                result.is_valid,
            )
            return result
        except NotFoundError:
            raise
        except Exception as e:
            logger.exception(
                "Freeze toggle repository call failed code=%s", code
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

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
            await self._verify_item_exists(code)

            deleted = await self._delete_item(session=self.session, code=code)
            if not deleted:
                message = f"Failed to delete record with code {code}"
                logger.error(message)
                raise DatabaseError(message)

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
