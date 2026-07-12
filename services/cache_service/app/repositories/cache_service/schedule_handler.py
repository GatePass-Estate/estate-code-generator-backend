import json
import logging
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import HTTPException

from app.schemas.cache_service.schedule_schema import (
    ScheduleAddRequest,
    ScheduleAddResponse,
    ScheduleDueResponse,
    ScheduleRemoveRequest,
)

logger = logging.getLogger(__name__)


class ScheduleRepository:
    """Redis sorted-set repository for deferred task scheduling."""

    def __init__(self, session: redis.Redis) -> None:
        self.session = session

    async def add(self, request: ScheduleAddRequest) -> ScheduleAddResponse:
        """
        Add a task member to the sorted set identified by *key* with *score*
        as the Unix due-timestamp.

        Returns:
            ScheduleAddResponse with added=True if the member was new.

        Raises:
            HTTPException 500: On Redis error.
        """
        try:
            result = await self.session.zadd(
                request.key, {request.member: request.score}
            )
            logger.info(
                "Schedule added key=%s score=%s added=%s",
                request.key,
                request.score,
                result,
            )
            return ScheduleAddResponse(added=bool(result))
        except Exception as e:
            logger.exception("Schedule add failed key=%s", request.key)
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def get_due(self, key: str) -> ScheduleDueResponse:
        """
        Return all members whose score (Unix timestamp) is <= now.

        Args:
            key: The sorted-set key to query.

        Returns:
            ScheduleDueResponse with the list of due member strings.

        Raises:
            HTTPException 500: On Redis error.
        """
        try:
            now = datetime.now(timezone.utc).timestamp()
            items = await self.session.zrangebyscore(key, "-inf", now)
            logger.info(
                "Schedule get_due key=%s now=%s count=%s",
                key,
                now,
                len(items),
            )
            return ScheduleDueResponse(key=key, items=items)
        except Exception as e:
            logger.exception("Schedule get_due failed key=%s", key)
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def remove(self, key: str, request: ScheduleRemoveRequest) -> bool:
        """
        Remove a specific member from the sorted set.

        Returns:
            True if the member existed and was removed.

        Raises:
            HTTPException 500: On Redis error.
        """
        try:
            result = await self.session.zrem(key, request.member)
            logger.info("Schedule remove key=%s removed=%s", key, bool(result))
            return bool(result)
        except Exception as e:
            logger.exception("Schedule remove failed key=%s", key)
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def remove_by_field(
        self,
        key: str,
        field_name: str,
        field_value: str,
    ) -> bool:
        """
        Scan all members of the sorted set and ZREM the first member whose
        JSON payload contains {field_name: field_value}.

        Returns:
            True if a matching member was found and removed.

        Raises:
            HTTPException 500: On Redis error.
        """
        try:
            all_members = await self.session.zrange(key, 0, -1)
            for member in all_members:
                try:
                    data = json.loads(member)
                    if str(data.get(field_name)) == str(field_value):
                        await self.session.zrem(key, member)
                        logger.info(
                            "Schedule remove_by_field key=%s %s=%s",
                            key,
                            field_name,
                            field_value,
                        )
                        return True
                except (json.JSONDecodeError, AttributeError):
                    continue
            return False
        except Exception as e:
            logger.exception("Schedule remove_by_field failed key=%s", key)
            raise HTTPException(status_code=500, detail=str(e)) from e
