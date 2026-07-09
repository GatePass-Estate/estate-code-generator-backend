"""Frontend-facing visitor log history endpoints (BFF)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.libs.auth import get_current_user
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.schemas.visitor_log import ListResponse
from app.services.visitor_log import VisitorLogService as Service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> Service:
    """
    Get an instance of Service.

    Returns:
        Service: Instance of Service
    """
    return Service(ahttp_client=ahttp_client)


@router.get(
    "/me",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Security accounts have no personal history"},
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved the visitor history"},
    },
    description="View your own visitor history (one entry per code)",
)
async def my_history(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ListResponse:
    """
    First-level personal visitor history: one entry per unique code, latest
    first. Security accounts are not permitted.
    """
    try:
        return await service.my_history(
            requester=current_user,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "An unexpected error happened while getting the history"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/me/{code}",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Security accounts have no personal history"},
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved the code history"},
    },
    description="View all visit events linked to one of your codes",
)
async def my_history_by_code(
    code: str,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ListResponse:
    """
    Second-level personal visitor history for a single code, latest first.
    Security accounts are not permitted.
    """
    try:
        return await service.my_history_by_code(
            requester=current_user,
            hashed_code=code,
            page=page,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "An unexpected error happened while getting the code history"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/user",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Not authorized to view these logs"},
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved the visitor history"},
    },
    description="View estate-wide visitor history (one entry per code)",
)
async def estate_history(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ListResponse:
    """
    First-level estate-wide visitor history: one entry per unique code, latest
    first. Admin/security see their own estate; root sees all estates.
    """
    try:
        return await service.estate_history(
            requester=current_user,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "An unexpected error happened while getting the history"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/user/{code}",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Not authorized to view these logs"},
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved the code history"},
    },
    description="View all visit events linked to a specific code",
)
async def estate_history_by_code(
    code: str,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ListResponse:
    """
    Second-level estate-wide visitor history for a single code, latest first.
    Admin/security are limited to their own estate; root may look up any code.
    """
    try:
        return await service.estate_history_by_code(
            requester=current_user,
            hashed_code=code,
            page=page,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "An unexpected error happened while getting the code history"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
