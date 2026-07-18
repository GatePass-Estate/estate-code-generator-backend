import logging
from datetime import datetime

from pydantic import UUID4

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)


class VisitorLogRepository:
    """
    Fetches visitor-log history from db-service for the BFF.

    First-level queries use ``visitorlog/search`` with ``unique=true``; the
    db-service sets ``created_at`` from the earliest log row per code.
    Second-level queries filter by ``hashed_code``.
    """

    def __init__(self, ahttp_client: AsyncHttpHandler) -> None:
        """
        Initializes the repository with the provided HTTP handler.

        Arguments:
            ahttp_client: The async HTTP handler used to reach the db-service.
        """
        self.ahttp_client = ahttp_client
        self.endpoint = (
            f"{settings.DB_SERVICE_URL}api/v1/codeservice/visitorlog/search"
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
        First-level visitor history: one entry per unique code with
        ``usage_count``, latest first.

        Backed by db-service ``visitorlog/search`` with ``unique=true``. The
        db-service sets ``created_at`` from the earliest log row per code so
        first-level history reflects when the code was first used; other fields
        come from the most recent validation row.

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
        Second-level visitor history: every visit for one code, latest first.

        Backed by db-service ``visitorlog/search`` filtered by ``hashed_code``.

        Returns:
            Raw db-service list payload for :class:`ListResponse`.
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
