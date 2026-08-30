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
    AiSummaryPatchRequest,
    AiSummaryResponse,
    CaseDemographicResponse,
    CaseDetailResponse,
    CaseRequest,
    HistoryResponse,
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


@router.get(
    "/{prediction_id}/demographic",
    response_model=CaseDemographicResponse,
    responses={
        404: {"description": "Prediction not found"},
        500: {"description": "Internal server error"},
    },
)
async def case_demographic(
    prediction_id: UUID4,
    estate_id: UUID4,
    display_name: str | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    service: Service = Depends(get_service),
) -> CaseDemographicResponse:
    """
    Person-level demographic for a selected prediction case.

    ``user_id`` is set only for resident-side rows (display picture).
    ``total_entries`` counts visitor or resident logs for that name in
    the date window. ``average_entry_per_week`` divides that count by
    the window length in weeks (minimum one day).
    ``has_tier1_summary`` / ``has_tier2_summary`` report whether the
    prediction already has a cached in-house or LLM summary.

    Arguments:
        prediction_id: Selected prediction row.
        estate_id: Estate that owns the visitor or resident log.
        display_name: Optional name override; defaults to the joined log.
        from_date: Inclusive lower bound on log timestamps.
        to_date: Inclusive upper bound on log timestamps.

    Returns:
        Name, user type, optional user id, total entries, weekly rate,
        and ``has_tier1_summary`` / ``has_tier2_summary`` cache flags.

    Raises:
        HTTPException: 404 if the prediction is not in the estate; 500
            on unexpected database or server errors.
    """
    try:
        request = CaseRequest(
            prediction_id=prediction_id,
            estate_id=estate_id,
            display_name=display_name,
            from_date=from_date,
            to_date=to_date,
        )
        return await service.case_demographic(request)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("case demographic prediction result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/{prediction_id}/history",
    response_model=HistoryResponse,
    responses={
        404: {"description": "Prediction not found"},
        500: {"description": "Internal server error"},
    },
)
async def case_history(
    prediction_id: UUID4,
    estate_id: UUID4,
    display_name: str | None = None,
    history_limit: int = Query(default=5, ge=1, le=20),
    service: Service = Depends(get_service),
) -> HistoryResponse:
    """
    Recent predictions for the same visitor or resident name.

    The selected instance is the newest row returned. Matches
    ``visitor_fullname`` or ``residentlog.full_name`` (case-insensitive)
    and ``created_at <=`` the selected prediction.

    Arguments:
        prediction_id: Selected prediction (most recent in the list).
        estate_id: Estate that owns the visitor or resident log.
        display_name: Optional name override; defaults to the joined log.
        history_limit: Max rows; default 5.

    Returns:
        Validation timestamp, validated code, and severity per row.

    Raises:
        HTTPException: 404 if the prediction is not in the estate; 500
            on unexpected database or server errors.
    """
    try:
        request = CaseRequest(
            prediction_id=prediction_id,
            estate_id=estate_id,
            display_name=display_name,
            history_limit=history_limit,
        )
        return await service.case_history(request)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("case history prediction result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get(
    "/{prediction_id}/case",
    response_model=CaseDetailResponse,
    responses={
        404: {"description": "Prediction not found"},
        500: {"description": "Internal server error"},
    },
)
async def case_detail(
    prediction_id: UUID4,
    estate_id: UUID4,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    service: Service = Depends(get_service),
) -> CaseDetailResponse:
    """
    Selected prediction payload plus period sample and max maps.

    Consumed by ai-service case results and summary. ``normal_sample``
    and max maps use the same window rules as overview.

    Arguments:
        prediction_id: Selected prediction row.
        estate_id: Estate that owns the visitor or resident log.
        from_date: Inclusive lower bound on prediction time.
        to_date: Inclusive upper bound on prediction time.

    Returns:
        Result JSON, cached ``ai_summary`` flags, sample, and max maps.

    Raises:
        HTTPException: 404 if the prediction is not in the estate; 500
            on unexpected database or server errors.
    """
    try:
        request = CaseRequest(
            prediction_id=prediction_id,
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
        )
        return await service.case_detail(request)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("case detail prediction result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch(
    "/{prediction_id}/ai-summary",
    response_model=AiSummaryResponse,
    responses={
        404: {"description": "Prediction not found"},
        500: {"description": "Internal server error"},
    },
)
async def patch_ai_summary(
    prediction_id: UUID4,
    body: AiSummaryPatchRequest,
    service: Service = Depends(get_service),
) -> AiSummaryResponse:
    """
    Merge generated summaries into the prediction's ``ai_summary`` JSON.

    Only provided keys are written; existing tier payloads are kept.

    Arguments:
        prediction_id: Prediction row to update.
        body: Optional ``tier1`` and/or ``tier2`` report objects.

    Returns:
        Stored ``ai_summary`` and presence flags.

    Raises:
        HTTPException: 404 if the prediction is not found; 500 on
            unexpected database or server errors.
    """
    try:
        return await service.patch_ai_summary(prediction_id, body)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("patch ai_summary prediction result")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
