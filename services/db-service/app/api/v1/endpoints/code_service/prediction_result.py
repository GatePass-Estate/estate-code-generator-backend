"""HTTP API for prediction-result list and result-page overview."""

import datetime
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.code_service.prediction_result import (
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    SearchRequest,
    Severity,
    UserType,
)
from app.schemas.code_service.visitor_log import Gender
from app.services.code_service.prediction_result import (
    PredictionResultService as Service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    """Build a ``PredictionResultService`` bound to this request session."""
    return Service(db_session=db_session)


@router.get(
    "/search",
    response_model=ListResponse,
    responses={500: {"description": "Internal server error"}},
)
async def search(
    estate_id: UUID4,
    severity: list[Severity] | None = Query(default=None),
    gender: list[Gender] | None = Query(default=None),
    user_type: list[UserType] | None = Query(default=None),
    sort_order: Literal["asc", "desc"] = "desc",
    is_anomalous: bool | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    page: int = 1,
    limit: int = 10,
    service: Service = Depends(get_service),
) -> ListResponse:
    """
    List prediction-result rows for an estate.

    Consumed by ai-service result-page predictions. Repeat
    ``severity``, ``gender``, and ``user_type`` to OR multiple values
    within that category; omitted categories are unfiltered. Categories
    AND with each other. Sorted by ``created_at``.

    Severity is derived from stored ``final_score``: low < 0.5, medium
    0.5 to 0.8, high >= 0.8. ``user_type=resident`` is role resident,
    admin, or primary_admin. ``gender`` matches visitor-log gender for
    guests and user-profile gender for residents.

    Arguments:
        estate_id: Estate to scope the list.
        severity: One or more of low, medium, high.
        gender: One or more of male, female, prefer_not_to_say.
        user_type: One or more of guest, resident.
        sort_order: Sort by created_at; default desc.
        is_anomalous: Filter on stored is_anomalous when set.
        from_date: Inclusive lower bound on created_at.
        to_date: Inclusive upper bound on created_at.
        page: 1-based page number.
        limit: Page size.

    Returns:
        Paginated list items with score, severity, user type, gender,
        and display name.

    Raises:
        HTTPException: 500 on unexpected database or server errors.
    """
    try:
        request = SearchRequest(**vars())
        return await service.search(request=request, page=page, limit=limit)
    except Exception as e:
        logger.exception("search prediction result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/overview",
    response_model=OverviewResponse,
    responses={
        404: {"description": "Estate not found"},
        500: {"description": "Internal server error"},
    },
)
async def overview(
    estate_id: UUID4,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    service: Service = Depends(get_service),
) -> OverviewResponse:
    """
    Estate counts, a 30% non-anomalous sample, and period max values.

    Consumed by ai-service result-page overview. This endpoint returns
    raw SQL aggregates and JSON payloads; ai-service reshapes them into
    demographic, evidence, spider-plot, and contributing-factor fields.

    Prediction rows are filtered by ``created_at`` in ``from_date`` /
    ``to_date``. Guest uniqueness uses visitor-log ``visit_time``.
    Resident-side users are role resident, admin, or primary_admin.
    Anomalous and high-risk fields are prediction row counts
    (``final_score >= 0.8`` is high-risk). ``normal_sample`` is a random
    30% of non-anomalous ``result`` JSON. Max maps cover *all*
    predictions in the window, including anomalous: feature values,
    scope scores, and per-scope feature values.

    Arguments:
        estate_id: Estate to summarise.
        from_date: Inclusive lower bound on prediction time.
        to_date: Inclusive upper bound on prediction time.

    Returns:
        Estate identity, demographic counts, anomalous-instance counts,
        ``normal_sample``, ``feature_max_values``, ``scope_max_scores``,
        and ``scope_feature_max_values``.

    Raises:
        HTTPException: 404 if the estate does not exist; 500 on
            unexpected database or server errors.
    """
    try:
        request = OverviewRequest(**vars())
        # SQL counts + normal_sample; payload reshaped in ai-service
        return await service.overview(request)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("overview prediction result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
