from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify
from app.repositories.incident_report import IncidentReportRepository
from app.schemas.incident_report import (
    CreateIncidentReportRequest,
    CreateIncidentReportResponse,
    IncidentCategory,
    IncidentReportItem,
    IncidentReportListResponse,
)
from app.services.auth import get_current_user
from app.services.incident_report import IncidentReportService

router = APIRouter()


def get_service(
    http_client: AsyncHttpHandler = Depends(get_http_handler),
) -> IncidentReportService:
    return IncidentReportService(IncidentReportRepository(http_client))


@router.get("/categories", response_model=list[str])
async def list_categories(
    service: IncidentReportService = Depends(get_service),
) -> list[str]:
    """Return all valid incident category values."""
    return await service.categories()


@router.post("", response_model=CreateIncidentReportResponse)
async def create(
    request: CreateIncidentReportRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> CreateIncidentReportResponse:
    """File a new incident report. Any authenticated user may file."""
    result = await service.create(
        request,
        estate_id=str(current_user["estate_id"]),
        user_id=str(current_user["id"]),
    )
    background_tasks.add_task(
        fire_notify,
        {
            "type": "INCIDENT_REPORT_FILED",
            "title": "New Incident Report",
            "body": "A new incident report has been filed.",
            "fan_out": {
                "estate_id": str(current_user["estate_id"]),
                "roles": ["admin", "primary_admin"],
            },
            "metadata": {
                "incident_id": str(result.id),
                "title": request.title or "Incident Report",
            },
        },
    )
    return result


@router.get("", response_model=IncidentReportListResponse)
async def list_all(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> IncidentReportListResponse:
    """List non-cleared incident reports. Admins only."""
    return await service.list(
        admin_id=str(current_user["id"]),
        user_role=current_user["role"],
        user_estate_id=str(current_user["estate_id"]),
        page=page,
        limit=limit,
    )


@router.get("/search", response_model=IncidentReportListResponse)
async def search(
    category: Optional[IncidentCategory] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> IncidentReportListResponse:
    """Search incident reports with optional filters. Admins only."""
    return await service.search(
        admin_id=str(current_user["id"]),
        user_role=current_user["role"],
        user_estate_id=str(current_user["estate_id"]),
        category=category.value if category else None,
        from_date=from_date,
        to_date=to_date,
        page=page,
        limit=limit,
    )


@router.get("/{incident_id}", response_model=IncidentReportItem)
async def get(
    incident_id: str,
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> IncidentReportItem:
    """Get a single incident report with reporter details. Admins only."""
    return await service.get(
        incident_id,
        admin_id=str(current_user["id"]),
        user_role=current_user["role"],
        user_estate_id=str(current_user["estate_id"]),
    )


@router.post("/{incident_id}/read", response_model=dict)
async def mark_read(
    incident_id: str,
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> dict:
    """Mark a single incident report as read. Admins only."""
    return await service.mark_read(
        incident_id,
        admin_id=str(current_user["id"]),
        user_role=current_user["role"],
    )


@router.post("/read-all", response_model=dict)
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> dict:
    """Bulk-mark all uncleared reports as read. Admins only."""
    return await service.mark_all_read(
        admin_id=str(current_user["id"]),
        estate_id=str(current_user["estate_id"]),
        user_role=current_user["role"],
    )


@router.delete("/clear-read", response_model=dict)
async def clear_read(
    current_user: dict = Depends(get_current_user),
    service: IncidentReportService = Depends(get_service),
) -> dict:
    """Soft-delete all read records for this admin. Admins only."""
    return await service.clear_read(
        admin_id=str(current_user["id"]),
        estate_id=str(current_user["estate_id"]),
        user_role=current_user["role"],
    )
