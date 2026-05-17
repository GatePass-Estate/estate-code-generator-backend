import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.code_service.incident_report import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    IncidentCategory,
    ListResponse,
    SearchRequest,
)
from app.services.code_service.incident_report import (
    IncidentReportService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    return Service(db_session=db_session)


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
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/search",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
)
async def search(
    estate_id: UUID4 | None = None,
    reported_by_user_id: UUID4 | None = None,
    category: IncidentCategory | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    page: int = 1,
    limit: int = 100,
    service: Service = Depends(get_service),
) -> ListResponse:
    try:
        request = SearchRequest(**vars())
        return await service.search(request=request, page=page, limit=limit)
    except Exception as e:
        logger.exception("Unexpected error searching incident reports")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{id}",
    response_model=GetResponse,
    status_code=status.HTTP_200_OK,
)
async def get(
    id: UUID4,
    service: Service = Depends(get_service),
) -> GetResponse:
    try:
        return await service.get(id=id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("Unexpected error getting incident report")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_all(
    page: int | None = 1,
    limit: int | None = 20,
    service: Service = Depends(get_service),
) -> ListResponse:
    try:
        return await service.list(page=page, limit=limit)
    except Exception as e:
        logger.exception("Unexpected error listing incident reports")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
