from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException

from app.repositories.incident_report import IncidentReportRepository
from app.schemas.incident_report import (
    CreateIncidentReportRequest,
    CreateIncidentReportResponse,
    IncidentReportItem,
    IncidentReportListResponse,
)

logger = logging.getLogger(__name__)


class IncidentReportService:
    def __init__(self, repository: IncidentReportRepository) -> None:
        self.repository = repository

    async def categories(self) -> list[str]:
        return await self.repository.categories()

    async def create(
        self,
        request: CreateIncidentReportRequest,
        *,
        estate_id: str,
        user_id: str,
    ) -> CreateIncidentReportResponse:
        return await self.repository.create(
            estate_id=estate_id,
            reported_by_user_id=user_id,
            title=request.title,
            category=[c.value for c in request.category],
            custom_category=request.custom_category,
            narrative=request.narrative,
            occurred_at=request.occurred_at.isoformat(),
        )

    async def get(
        self,
        incident_id: str,
        admin_id: str,
        *,
        user_role: str,
        user_estate_id: str,
    ) -> IncidentReportItem:
        _require_admin(user_role)
        item = await self.repository.get(incident_id, admin_id)
        _require_same_estate(str(item.estate_id), user_estate_id)
        return item

    async def list(
        self,
        admin_id: str,
        *,
        user_role: str,
        user_estate_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> IncidentReportListResponse:
        _require_admin(user_role)
        # Use search with estate_id to ensure estate-scoped results.
        return await self.repository.search(
            estate_id=user_estate_id,
            admin_id=admin_id,
            page=page,
            limit=limit,
        )

    async def search(
        self,
        admin_id: str,
        *,
        user_role: str,
        user_estate_id: str,
        category: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> IncidentReportListResponse:
        _require_admin(user_role)
        return await self.repository.search(
            estate_id=user_estate_id,
            admin_id=admin_id,
            category=category,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )

    async def mark_read(
        self,
        incident_id: str,
        admin_id: str,
        *,
        user_role: str,
    ) -> dict:
        _require_admin(user_role)
        return await self.repository.mark_read(incident_id, admin_id)

    async def mark_all_read(
        self,
        admin_id: str,
        estate_id: str,
        *,
        user_role: str,
    ) -> dict:
        _require_admin(user_role)
        return await self.repository.mark_all_read(
            estate_id=estate_id, admin_id=admin_id
        )

    async def clear_read(
        self,
        admin_id: str,
        estate_id: str,
        *,
        user_role: str,
    ) -> dict:
        _require_admin(user_role)
        return await self.repository.clear_read(
            estate_id=estate_id, admin_id=admin_id
        )


def _require_admin(role: str) -> None:
    if role not in ("admin", "primary_admin", "root"):
        raise HTTPException(
            status_code=403,
            detail="Only admins can access incident reports.",
        )


def _require_same_estate(report_estate_id: str, user_estate_id: str) -> None:
    if report_estate_id != user_estate_id:
        raise HTTPException(
            status_code=403,
            detail="Access to reports from other estates is not allowed.",
        )
