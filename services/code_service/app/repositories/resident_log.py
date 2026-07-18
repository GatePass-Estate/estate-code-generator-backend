import logging
from datetime import datetime

from pydantic import UUID4

from app.core.config import settings
from app.libs.auth import get_user_details
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100


class ResidentLogRepository:
    """
    Fetches resident access-log history from db-service for the BFF.

    First-level queries use ``accesscode/search`` (one row per generated code
    with accurate ``created_at``), enriched from ``residentlog/search`` with
    ``unique=true`` for validation metadata. Second-level queries filter by
    ``hashed_code``; the service layer may additionally call
    :meth:`earliest_access_code` to enrich code-level responses.
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

    @staticmethod
    def _norm_hash(hashed_code: str) -> str:
        return hashed_code.strip().lower()

    async def _unique_log_map(
        self,
        *,
        user_id: UUID4 | str | None = None,
        estate_id: UUID4 | str | None = None,
    ) -> dict[str, dict]:
        """Fetch all unique resident-log rows keyed by ``hashed_code``."""
        params: dict = {
            "unique": True,
            "ascending": False,
            "page": 1,
            "limit": _PAGE_SIZE,
        }
        if user_id is not None:
            params["user_id"] = str(user_id)
        if estate_id is not None:
            params["estate_id"] = str(estate_id)

        by_hash: dict[str, dict] = {}
        page = 1
        while True:
            params["page"] = page
            result = await self.ahttp_client.async_get(
                self.endpoint, params=params
            )
            items = result.get("items") or []
            for item in items:
                hashed_code = item.get("hashed_code")
                if isinstance(hashed_code, str):
                    by_hash[self._norm_hash(hashed_code)] = item
            total = int(result.get("total") or 0)
            if not items or page * _PAGE_SIZE >= total:
                break
            page += 1
        return by_hash

    async def _resolve_full_name(self, user_id: str | None) -> str | None:
        """Look up a resident display name when log rows lack ``full_name``."""
        if not user_id:
            return None
        try:
            user = await get_user_details(self.ahttp_client, str(user_id))
        except Exception:
            logger.exception(
                "Failed to resolve resident name for user %s", user_id
            )
            return None
        name = (
            f"{user.get('first_name', '') or ''} "
            f"{user.get('last_name', '') or ''}"
        ).strip()
        return name or None

    async def _enrich_item_full_names(self, items: list[dict]) -> None:
        """Fill missing ``full_name`` values from ``user_id`` on each item."""
        cache: dict[str, str | None] = {}
        for item in items:
            existing = item.get("full_name")
            if isinstance(existing, str) and existing.strip():
                continue
            uid = str(item.get("user_id") or "")
            if not uid:
                continue
            if uid not in cache:
                cache[uid] = await self._resolve_full_name(uid)
            item["full_name"] = cache[uid]

    @staticmethod
    def _build_unique_item(access_code: dict, log: dict | None) -> dict:
        """Map an access-code row plus optional log metadata to a list item."""
        hashed_code = access_code["hashed_code"]
        item = {
            "id": access_code["id"],
            "created_at": access_code["created_at"],
            "updated_at": (
                log["updated_at"] if log else access_code["updated_at"]
            ),
            "user_id": access_code["user_id"],
            "estate_id": access_code["estate_id"],
            "hashed_code": hashed_code,
            "code_deleted": bool(access_code.get("is_deleted")),
            "usage_count": int(log.get("usage_count") or 0) if log else 0,
        }
        if log:
            item["security_id"] = log["security_id"]
            item["access_time"] = log["access_time"]
            log_name = log.get("full_name")
            item["full_name"] = (
                log_name.strip()
                if isinstance(log_name, str) and log_name.strip()
                else None
            )
        else:
            item["security_id"] = access_code["user_id"]
            item["access_time"] = access_code["created_at"]
            item["full_name"] = None
        return item

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
        First-level history: one entry per access code with ``usage_count`` and
        ``code_deleted``, latest first.

        Backed by db-service ``accesscode/search`` so ``created_at`` reflects
        when the code was generated. Validation metadata (``usage_count``,
        ``access_time``, ``security_id``, ``full_name``) is merged from
        ``residentlog/search`` with ``unique=true`` when present.

        Scope is controlled by ``user_id`` (personal) or ``estate_id``
        (estate-wide); passing neither returns all estates. Date filters apply
        to access-code ``created_at``.

        Arguments:
            user_id: Restrict to a single resident's history.
            estate_id: Restrict to a single estate's history.
            from_date: Filter access codes created on or after this timestamp.
            to_date: Filter access codes created on or before this timestamp.
            page: The page number to retrieve.
            limit: The number of items per page.

        Returns:
            Raw db-service list payload for :class:`ListResponse`.
        """
        params: dict = {
            "include_deleted": True,
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

        access_result = await self.ahttp_client.async_get(
            self.access_code_endpoint, params=params
        )
        log_map = await self._unique_log_map(
            user_id=user_id,
            estate_id=estate_id,
        )
        items = [
            self._build_unique_item(
                access_code,
                log_map.get(self._norm_hash(access_code["hashed_code"])),
            )
            for access_code in access_result.get("items") or []
        ]
        await self._enrich_item_full_names(items)
        return {
            "total": access_result.get("total"),
            "page": access_result.get("page"),
            "limit": access_result.get("limit"),
            "items": items,
        }

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
