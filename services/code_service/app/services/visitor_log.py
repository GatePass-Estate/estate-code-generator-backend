import logging
from datetime import datetime

from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.libs.revenue_entitlements import (
    VISITOR_LOG_RETENTION_KEY,
    resolve_retention_from_date,
)
from app.libs.role_permissions import get_role_permissions
from app.repositories.visitor_log import (
    VisitorLogRepository as Repository,
)
from app.schemas.visitor_log import ListResponse

logger = logging.getLogger(__name__)


class VisitorLogService:
    """
    BFF service for visitor-log history exposed under
    ``/codeservice/visitorlog``.

    Two retrieval levels:

    * **First level** (``/me``, ``/user``): one entry per unique
      ``hashed_code`` with ``usage_count``; ``created_at`` is the earliest log
      row per code (db-service ``unique=true``).
    * **Second level** (``/me/{code}``, ``/user/{code}``): every visit for a
      single code, latest first.

    Personal endpoints reject security accounts (in-code check). Estate-wide
    endpoints require ``can_view_other_user_logs`` (admin/security within
    estate; root globally). Each entry carries denormalized
    ``resident_fullname``.

    History windows are clamped by revenue-service
    ``visitor_log_retention_days`` when an estate_id is known.
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

    async def _apply_retention(
        self,
        estate_id: str | None,
        from_date: datetime | None,
    ) -> datetime | None:
        """Clamp from_date using visitor_log_retention_days when estate is known."""
        if not estate_id:
            return from_date
        return await resolve_retention_from_date(
            self.ahttp_client,
            estate_id=str(estate_id),
            service_key=VISITOR_LOG_RETENTION_KEY,
            from_date=from_date,
        )

    @staticmethod
    def _reject_personal_for_security(requester: dict) -> None:
        """
        Block security staff from the personal (``me/``) endpoints.

        Security accounts validate codes but do not own visitor history, so a
        personal view is meaningless for them.

        Raises:
            HTTPException: 403 if the requester is a security account.
        """
        if str(requester.get("role", "")).lower() == "security":
            raise HTTPException(
                status_code=403,
                detail="Security accounts have no personal visitor history.",
            )

    async def my_history(
        self,
        requester: dict,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponse:
        """
        First-level personal visitor history: one entry per unique code with
        ``usage_count``; ``created_at`` reflects the earliest log row per
        code. Security accounts are rejected.
        """
        self._reject_personal_for_security(requester)
        estate_id = requester.get("estate_id")
        effective_from = await self._apply_retention(
            str(estate_id) if estate_id else None, from_date
        )
        result = await self.repository.unique_history(
            user_id=requester["id"],
            from_date=effective_from,
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
    ) -> ListResponse:
        """
        Second-level personal visitor history for one ``hashed_code``, latest
        first. Security accounts are rejected.
        """
        self._reject_personal_for_security(requester)
        estate_id = requester.get("estate_id")
        effective_from = await self._apply_retention(
            str(estate_id) if estate_id else None, None
        )
        result = await self.repository.code_history(
            hashed_code=hashed_code,
            user_id=requester["id"],
            from_date=effective_from,
            page=page,
            limit=limit,
        )
        return ListResponse.model_validate(result)

    async def estate_history(
        self,
        requester: dict,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponse:
        """
        First-level estate-wide visitor history: one entry per unique code with
        ``usage_count``; ``created_at`` reflects the earliest log row per
        code. Requires permission to view other users' logs.
        """
        estate_scope = await self._resolve_estate_scope(requester)
        effective_from = await self._apply_retention(estate_scope, from_date)
        result = await self.repository.unique_history(
            estate_id=estate_scope,
            from_date=effective_from,
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
    ) -> ListResponse:
        """
        Second-level estate-wide visitor history for one ``hashed_code``,
        latest first. Requires permission to view other users' logs.
        """
        estate_scope = await self._resolve_estate_scope(requester)
        effective_from = await self._apply_retention(estate_scope, None)
        result = await self.repository.code_history(
            hashed_code=hashed_code,
            estate_id=estate_scope,
            from_date=effective_from,
            page=page,
            limit=limit,
        )
        return ListResponse.model_validate(result)
