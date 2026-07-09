import logging
from datetime import datetime

from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.libs.role_permissions import get_role_permissions
from app.repositories.resident_log import (
    ResidentLogRepository as Repository,
)
from app.schemas.resident_log import CodeHistoryListResponse, ListResponse

logger = logging.getLogger(__name__)


class ResidentLogService:
    """
    BFF service for resident access-log history exposed under
    ``/codeservice/residentlog``.

    Two retrieval levels are supported:

    * **First level** (``/me``, ``/user``): one entry per unique
      ``hashed_code``, latest first; returns :class:`ListResponse`.
    * **Second level** (``/me/{code}``, ``/user/{code}``): every validation
      for a single code, latest first, plus the earliest access-code creation
      row when the page covers it; returns :class:`CodeHistoryListResponse`
      with ``code_deleted``.

    Personal endpoints reject security accounts (in-code check). Estate-wide
    endpoints require ``can_view_other_user_logs`` (admin/security within
    estate; root globally). Each entry carries the resident's denormalized
    ``full_name``.
    """

    def __init__(self, ahttp_client: AsyncHttpHandler) -> None:
        self.ahttp_client = ahttp_client
        self.repository = Repository(ahttp_client)

    async def _resolve_estate_scope(self, requester: dict) -> str | None:
        """
        Authorize an estate-wide request and return the estate scope to apply.

        Returns:
            The requester's estate_id when they may only view their own estate,
            or None when they may view all estates (root).

        Raises:
            HTTPException: 403 if the requester may not view others' logs.
        """
        permissions = await get_role_permissions(
            self.ahttp_client, requester["role"]
        )
        if not permissions.get("can_view_other_user_logs", False):
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view these logs.",
            )
        if permissions.get("can_view_other_user_logs_in_other_estate", False):
            return None
        estate_id = requester.get("estate_id")
        if not estate_id:
            raise HTTPException(
                status_code=403,
                detail="No estate is associated with your account.",
            )
        return str(estate_id)

    @staticmethod
    def _reject_personal_for_security(requester: dict) -> None:
        """
        Block security staff from the personal (``me/``) endpoints.

        Security accounts validate codes but do not own access history, so a
        personal view is meaningless for them.

        Raises:
            HTTPException: 403 if the requester is a security account.
        """
        if str(requester.get("role", "")).lower() == "security":
            raise HTTPException(
                status_code=403,
                detail="Security accounts have no personal access history.",
            )

    @staticmethod
    def _access_code_to_log_entry(
        access_code: dict,
        full_name: str | None,
    ) -> dict:
        """Map the earliest access-code row to a code-level history list item."""
        created_at = access_code["created_at"]
        return {
            "id": access_code["id"],
            "created_at": created_at,
            "updated_at": access_code["updated_at"],
            "user_id": access_code["user_id"],
            "estate_id": access_code["estate_id"],
            "hashed_code": access_code["hashed_code"],
            "security_id": None,
            "access_time": created_at,
            "full_name": full_name,
        }

    async def _enrich_code_history(
        self,
        result: dict,
        hashed_code: str,
        page: int,
        limit: int,
    ) -> dict:
        """
        Enrich a code-level history payload.

        Looks up the earliest access-code row (including soft-deleted) and
        sets ``code_deleted``. Appends a synthetic creation row as the last
        item when the current page covers the chronologically earliest slot in
        the latest-first combined timeline. Used only for
        :class:`CodeHistoryListResponse`.
        """
        access_code = await self.repository.earliest_access_code(hashed_code)
        if not access_code:
            result["code_deleted"] = False
            return result

        result["code_deleted"] = bool(access_code.get("is_deleted"))

        items = list(result.get("items") or [])
        full_name = next(
            (item.get("full_name") for item in items if item.get("full_name")),
            None,
        )
        genesis = self._access_code_to_log_entry(access_code, full_name)

        total_logs = int(result.get("total") or 0)
        genesis_index = total_logs
        start = (page - 1) * limit
        end = page * limit

        if start <= genesis_index < end:
            items.append(genesis)
            result["items"] = items
            result["total"] = total_logs + 1

        return result

    async def my_history(
        self,
        requester: dict,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponse:
        """
        First-level personal history: one entry per unique code, latest first.

        Returns :class:`ListResponse` without ``code_deleted``. Security
        accounts are rejected.
        """
        self._reject_personal_for_security(requester)
        result = await self.repository.unique_history(
            user_id=requester["id"],
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
        return ListResponse.model_validate(result)

    async def my_history_by_code(
        self,
        requester: dict,
        hashed_code: str,
        page: int = 1,
        limit: int = 20,
    ) -> CodeHistoryListResponse:
        """
        Second-level personal history for one ``hashed_code``.

        Returns :class:`CodeHistoryListResponse` with validation rows (latest
        first), optional appended code-creation row, and ``code_deleted``.
        Security accounts are rejected.
        """
        self._reject_personal_for_security(requester)
        result = await self.repository.code_history(
            hashed_code=hashed_code,
            user_id=requester["id"],
            page=page,
            limit=limit,
        )
        result = await self._enrich_code_history(
            result, hashed_code, page, limit
        )
        return CodeHistoryListResponse.model_validate(result)

    async def estate_history(
        self,
        requester: dict,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponse:
        """
        First-level estate-wide history: one entry per unique code, latest
        first. Returns :class:`ListResponse` without ``code_deleted``.
        Requires permission to view other users' logs.
        """
        estate_scope = await self._resolve_estate_scope(requester)
        result = await self.repository.unique_history(
            estate_id=estate_scope,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
        return ListResponse.model_validate(result)

    async def estate_history_by_code(
        self,
        requester: dict,
        hashed_code: str,
        page: int = 1,
        limit: int = 20,
    ) -> CodeHistoryListResponse:
        """
        Second-level estate-wide history for one ``hashed_code``.

        Returns :class:`CodeHistoryListResponse` with validation rows (latest
        first), optional appended code-creation row, and ``code_deleted``.
        Requires permission to view other users' logs.
        """
        estate_scope = await self._resolve_estate_scope(requester)
        result = await self.repository.code_history(
            hashed_code=hashed_code,
            estate_id=estate_scope,
            page=page,
            limit=limit,
        )
        result = await self._enrich_code_history(
            result, hashed_code, page, limit
        )
        return CodeHistoryListResponse.model_validate(result)
