import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.user_profile.broadcast_reads import (
    CreateRequest,
    CreateResponse,
    DismissAllRequest,
    DismissRequest,
    ListResponse,
    SearchRequest,
)
from app.schemas.user_profile.notifications import UnreadCountResponse
from app.services.user_profile.broadcast_reads import (
    BroadcastReadsService as Service,
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
    description="Mark a broadcast as read (idempotent)",
)
async def mark_read(
    request: CreateRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    try:
        return await service.mark_read(request=request)
    except Exception as e:
        logger.exception("Unexpected error marking broadcast as read")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/dismiss",
    response_model=CreateResponse,
    status_code=status.HTTP_200_OK,
    description="Dismiss a single broadcast for a user",
)
async def dismiss(
    request: DismissRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    try:
        return await service.dismiss(request=request)
    except Exception as e:
        logger.exception("Unexpected error dismissing broadcast")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/dismiss-all",
    status_code=status.HTTP_200_OK,
    description="Dismiss all BROADCAST-category broadcasts for a user",
)
async def dismiss_all(
    request: DismissAllRequest,
    service: Service = Depends(get_service),
) -> dict:
    try:
        return await service.dismiss_all(request=request)
    except Exception as e:
        logger.exception("Unexpected error dismissing all broadcasts")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    description="Count unread broadcasts for a user",
)
async def unread_count(
    user_id: UUID4,
    estate_id: UUID4,
    roles: List[str] = Query(default=[]),
    service: Service = Depends(get_service),
) -> UnreadCountResponse:
    try:
        return await service.unread_count(
            user_id=user_id, estate_id=estate_id, roles=roles
        )
    except Exception as e:
        logger.exception("Unexpected error counting unread broadcasts")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    description="Search broadcast read records",
)
async def search(
    broadcast_id: Optional[UUID4] = None,
    user_id: Optional[UUID4] = None,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
) -> ListResponse:
    try:
        request = SearchRequest(
            broadcast_id=broadcast_id,
            user_id=user_id,
            page=page,
            limit=limit,
        )
        return await service.search(request=request)
    except Exception as e:
        logger.exception("Unexpected error searching broadcast reads")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
