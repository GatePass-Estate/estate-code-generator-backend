import logging
from typing import List

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)

_SCHEDULES_ENDPOINT = "api/v1/cacheservice/schedules"

# Sorted-set keys used for deferred task scheduling
SCHEDULED_USER_CLOSURES_KEY = "scheduled_user_closures"
SCHEDULED_ESTATE_DEACTIVATIONS_KEY = "scheduled_estate_deactivations"


class ScheduleRepository:
    """
    HTTP client for the cache_service scheduled-task sorted-set API.

    Methods:
        add: Add a task with a Unix-timestamp due score.
        get_due: Return all tasks whose score <= now.
        remove: Remove a specific task member.
    """

    def __init__(self, http_client: AsyncHttpHandler) -> None:
        self.client = http_client
        self.base_url = settings.CACHE_SERVICE_URL
        self.endpoint = f"{self.base_url}{_SCHEDULES_ENDPOINT}"

    async def add(self, key: str, score: float, member: str) -> bool:
        """
        Add *member* to the sorted set *key* with Unix-timestamp *score*.

        Returns:
            True if the member was newly added.

        Raises:
            HTTPException 500: If the cache_service call fails.
        """
        response = await self.client.async_post(
            self.endpoint,
            json_data={"key": key, "score": score, "member": member},
        )
        if response is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add schedule entry for key={key}",
            )
        return response.get("added", False)

    async def get_due(self, key: str) -> List[str]:
        """
        Return all member strings whose due timestamp is <= now.

        Args:
            key: The sorted-set key to query.

        Returns:
            List of JSON-serialised task payload strings.

        Raises:
            HTTPException 500: If the cache_service call fails.
        """
        url = f"{self.endpoint}/{key}/due"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch due schedules for key={key}",
            )
        return response.get("items", [])

    async def remove(self, key: str, member: str) -> bool:
        """
        Remove *member* from the sorted set *key*.

        Returns:
            True if the member existed and was removed.

        Raises:
            HTTPException 500: If the cache_service call fails.
        """
        url = f"{self.endpoint}/{key}"
        response = await self.client.async_delete(
            url, json_data={"member": member}
        )
        if response is None:
            logger.warning("Schedule remove returned no response key=%s", key)
            return False
        return bool(response)

    async def remove_by_field(
        self, key: str, field_name: str, field_value: str
    ) -> bool:
        """
        Remove the first sorted-set member whose JSON payload contains
        {field_name: field_value}.

        Returns:
            True if a matching member was removed.

        Raises:
            HTTPException 500: If the cache_service call fails.
        """
        from urllib.parse import urlencode

        params = urlencode(
            {"field_name": field_name, "field_value": field_value}
        )
        url = f"{self.endpoint}/{key}/by-field?{params}"
        response = await self.client.async_delete(url)
        if response is None:
            logger.warning(
                "Schedule remove_by_field returned no response key=%s", key
            )
            return False
        return bool(response)
