import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.user_profile.incident_report import (
    ClearReadRequest,
    CreateRequest,
    CreateResponse,
    GetResponseWithReadStatus,
    IncidentCategory,
    ListResponseWithReadStatus,
    MarkAllReadRequest,
    MarkReadRequest,
    SearchRequest,
)
from app.services.user_profile.incident_report import (
    IncidentReportService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    return Service(db_session=db_session)


@router.get(
    "/categories",
    response_model=List[str],
    status_code=status.HTTP_200_OK,
)
async def list_categories() -> List[str]:
    """Return all valid incident category values."""
    return [c.value for c in IncidentCategory]


@router.post(
    "",
    response_model=CreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    request: CreateRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    try:
        return await service.create(request=request)
    except Exception as e:
        logger.exception("Unexpected error creating incident report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/search",
    response_model=ListResponseWithReadStatus,
    status_code=status.HTTP_200_OK,
)
async def search(
    estate_id: Optional[UUID4] = None,
    reported_by_user_id: Optional[UUID4] = None,
    category: Optional[IncidentCategory] = None,
    from_date: Optional[datetime.datetime] = None,
    to_date: Optional[datetime.datetime] = None,
    admin_id: Optional[UUID4] = None,
    page: int = 1,
    limit: int = 100,
    service: Service = Depends(get_service),
) -> ListResponseWithReadStatus:
    try:
        request = SearchRequest(
            estate_id=estate_id,
            reported_by_user_id=reported_by_user_id,
            category=category,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
        return await service.search(
            request=request,
            admin_id=admin_id,
            page=page,
            limit=limit,
        )
    except Exception as e:
        logger.exception("Unexpected error searching incident reports")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/{id}",
    response_model=GetResponseWithReadStatus,
    status_code=status.HTTP_200_OK,
)
async def get(
    id: UUID4,
    admin_id: Optional[UUID4] = None,
    service: Service = Depends(get_service),
) -> GetResponseWithReadStatus:
    try:
        return await service.get(id=id, admin_id=admin_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident report not found",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error getting incident report id=%s", id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "",
    response_model=ListResponseWithReadStatus,
    status_code=status.HTTP_200_OK,
)
async def list_all(
    admin_id: UUID4,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
) -> ListResponseWithReadStatus:
    try:
        return await service.list(admin_id=admin_id, page=page, limit=limit)
    except Exception as e:
        logger.exception("Unexpected error listing incident reports")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post(
    "/{id}/read",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def mark_read(
    id: UUID4,
    request: MarkReadRequest,
    service: Service = Depends(get_service),
) -> dict:
    try:
        return await service.mark_read(request=request, incident_report_id=id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident report not found",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error marking incident %s as read", id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post(
    "/read-all",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def mark_all_read(
    request: MarkAllReadRequest,
    service: Service = Depends(get_service),
) -> dict:
    try:
        return await service.mark_all_read(request=request)
    except Exception as e:
        logger.exception(
            "Unexpected error bulk-marking incident reports as read"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete(
    "/clear-read",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def clear_read(
    request: ClearReadRequest,
    service: Service = Depends(get_service),
) -> dict:
    try:
        return await service.clear_read(request=request)
    except Exception as e:
        logger.exception("Unexpected error clearing read incident reports")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
