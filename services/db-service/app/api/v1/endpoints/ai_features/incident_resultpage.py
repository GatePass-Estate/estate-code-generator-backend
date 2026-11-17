"""HTTP API for the incident-report result page."""

import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.ai_features.incident_resultpage import (
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    SearchRequest,
)
from app.services.ai_features.incident_resultpage import (
    IncidentResultPageService as Service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    """Build an ``IncidentResultPageService`` for this request."""
    return Service(db_session=db_session)


@router.get(
    "/result-page/overview",
    response_model=OverviewResponse,
    responses={
        404: {"description": "Estate not found"},
        500: {"description": "Internal server error"},
    },
)
async def result_page_overview(
    estate_id: UUID4,
    from_date: Optional[datetime.datetime] = None,
    to_date: Optional[datetime.datetime] = None,
    service: Service = Depends(get_service),
) -> OverviewResponse:
    """
    Estate identity and reporter-role counts for the incident result page.

    ``resident_report_count`` includes every reporter role except
    security, guest, and root. ``security_report_count`` is security
    only. Date bounds filter on ``created_at``.

    Arguments:
        estate_id: Estate to summarise.
        from_date: Inclusive lower bound on created_at.
        to_date: Inclusive upper bound on created_at.

    Returns:
        Estate name, state, country, total reports, and role counts.

    Raises:
        HTTPException: 404 if the estate does not exist; 500 on
            unexpected database or server errors.
    """
    try:
        return await service.overview(
            OverviewRequest(
                estate_id=estate_id,
                from_date=from_date,
                to_date=to_date,
            )
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("result page overview incident report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/result-page/search",
    response_model=ListResponse,
    responses={500: {"description": "Internal server error"}},
)
async def result_page_search(
    estate_id: UUID4,
    categories: Optional[list[str]] = Query(default=None),
    user_types: Optional[list[str]] = Query(default=None),
    from_date: Optional[datetime.datetime] = None,
    to_date: Optional[datetime.datetime] = None,
    page: int = 1,
    limit: int = 10,
    service: Service = Depends(get_service),
) -> ListResponse:
    """
    List estate incidents for the result page.

    Repeat ``categories`` and ``user_types`` to OR multiple values
    within that filter; omitted filters are unfiltered.
    ``categories=all`` or ``user_types=all`` is the same as omitting
    that filter (every type). Filters AND with each other.
    ``user_types=resident`` is every role except security, guest,
    and root.

    Arguments:
        estate_id: Estate to list.
        categories: Taxonomy values, or ``all`` for every category.
        user_types: ``resident``, ``security``, or ``all``.
        from_date: Inclusive lower bound on created_at.
        to_date: Inclusive upper bound on created_at.
        page: 1-based page number.
        limit: Page size.

    Returns:
        Paginated incident rows plus ``reporter_user_type``.

    Raises:
        HTTPException: 500 on unexpected database or server errors.
    """
    try:
        request = SearchRequest(
            estate_id=estate_id,
            categories=categories,
            user_types=user_types,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
        return await service.search(request=request, page=page, limit=limit)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(),
        ) from e
    except Exception as e:
        logger.exception("result page search incident report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
