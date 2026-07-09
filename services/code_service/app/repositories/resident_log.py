import logging
from datetime import datetime

from pydantic import UUID4

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class ResidentLogRepository:
    """
    Fetches resident access-log history from db-service for the BFF.

    First-level queries use ``residentlog/search`` with ``unique=true``.
    Second-level queries filter by ``hashed_code``; the service layer may
    additionally call ``accesscode/search`` via :meth:`earliest_access_code`
    to enrich code-level responses.
    """

    def __init__(self, ahttp_client: AsyncHttpHandler) -> None:
        """
        Initializes the repository with the provided HTTP handler.

        Arguments:
            ahttp_client: The async HTTP handler used to reach the db-service.
        """
        self.ahttp_client = ahttp_client
        self.endpoint = (
            f"{settings.DB_SERVICE_URL}api/v1/codeservice/residentlog/search"
        )
        self.access_code_endpoint = (
            f"{settings.DB_SERVICE_URL}api/v1/codeservice/accesscode/search"
        )

    async def unique_history(
        self,
        *,
        user_id: UUID4 | str | None = None,
        estate_id: UUID4 | str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        First-level history: one entry per unique code with ``usage_count`` and
        ``code_deleted``, latest first.

        Backed by db-service ``residentlog/search`` with ``unique=true``.
        Scope is controlled by ``user_id`` (personal) or ``estate_id``
        (estate-wide); passing neither returns all estates.

        Arguments:
            user_id: Restrict to a single resident's history.
            estate_id: Restrict to a single estate's history.
            from_date: Filter access events on or after this timestamp.
            to_date: Filter access events on or before this timestamp.
            page: The page number to retrieve.
            limit: The number of items per page.

        Returns:
            Raw db-service list payload for :class:`ListResponse`.
        """
        params: dict = {
            "unique": True,
            "ascending": False,
            "page": page,
            "limit": limit,
        }
        if user_id is not None:
            params["user_id"] = str(user_id)
        if estate_id is not None:
            params["estate_id"] = str(estate_id)
        if from_date is not None:
            params["from_date"] = from_date.isoformat()
        if to_date is not None:
            params["to_date"] = to_date.isoformat()
        return await self.ahttp_client.async_get(self.endpoint, params=params)

    async def code_history(
        self,
        *,
        hashed_code: str,
        user_id: UUID4 | str | None = None,
        estate_id: UUID4 | str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        Second-level history: every validation for one code, latest first.
        Lifecycle metadata is added by the BFF service layer.

        Arguments:
            hashed_code: The specific access code to retrieve events for.
            user_id: Restrict to a single resident.
            estate_id: Restrict to a single estate.
            page: The page number to retrieve.
            limit: The number of items per page.

        Returns:
            Raw db-service list payload (validations only).
        """
        params: dict = {
            "hashed_code": hashed_code,
            "ascending": False,
            "page": page,
            "limit": limit,
        }
        if user_id is not None:
            params["user_id"] = str(user_id)
        if estate_id is not None:
            params["estate_id"] = str(estate_id)
        return await self.ahttp_client.async_get(self.endpoint, params=params)

    async def earliest_access_code(self, hashed_code: str) -> dict | None:
        """
        Earliest access-code row for ``hashed_code``, including soft-deleted.

        Used by the BFF to populate ``code_created_at``, ``code_deleted_at``,
        and ``code_deleted`` on code-level history.

        Returns:
            The first matching access-code dict ordered by ``created_at``, or
            ``None`` when no row exists.
        """
        params = {
            "hashed_code": hashed_code,
            "include_deleted": True,
            "ascending": True,
            "page": 1,
            "limit": 1,
        }
        result = await self.ahttp_client.async_get(
            self.access_code_endpoint, params=params
        )
        items = result.get("items") or []
        return items[0] if items else None
