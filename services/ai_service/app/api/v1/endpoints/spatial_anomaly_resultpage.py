"""HTTP routes for the spatial-anomaly result page."""

import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.exceptions import ResultPageError
from app.integrations.db_service_prediction_result import (
    fetch_overview,
    fetch_predictions,
)
from app.models.spatial_anomaly_resultpage import (
    PredictionListResponse,
    ResultPageOverviewResponse,
    Severity,
    UserType,
)
from app.pipeline.spatial_anomaly_resultpage import overview_from_db_payload

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/overview",
    response_model=ResultPageOverviewResponse,
)
async def get_result_page_overview(
    estate_id: UUID,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    current_user: dict = Depends(get_current_user),
) -> ResultPageOverviewResponse:
    """
    Build the spatial-anomaly result-page overview for one estate.

    Returns demographic counts, evidence totals, and expected-normal
    behaviour for the spider plot and contributing-factor sections.
    Requires a bearer token. Counts and the normal-behaviour sample are
    loaded from db-service; averaging, ranking, and scale are computed
    here.

    Date window (``from_date``, ``to_date``) filters prediction rows by
    ``created_at``. Guest uniqueness uses visitor-log ``visit_time`` in
    the same window. Omit both dates to include all retained data.

    Demographic
        ``estate_name``, ``state``, and ``country`` come from the estate
        record. ``total_guests`` is the count of unique
        ``visitor_fullname`` values in the window. ``total_users`` is
        active resident-side users (role resident, admin, or
        primary_admin) plus those unique guests. ``ratio`` is guest /
        resident / security counts and each group's percentage of
        guest + resident + security. ``total_anomalous_instances`` and
        ``total_high_risk_instances`` are prediction *row* counts, not
        unique people. High-risk is ``final_score >= 0.8``.

    Evidence summary
        ``total_anomalous_residents_instances`` counts anomalous rows
        with a resident log. ``total_anomalous_visitors_instances``
        counts anomalous rows with a visitor log.

    Anomaly overview
        Expected normal behaviour is the mean of a random 30% sample of
        *non-anomalous* predictions in the window. ``spider_plot`` and
        ``top_contributing_factors`` are the same top six features,
        ranked by mean weight (null weights sort last, then reverse
        feature name). ``contributing_factors`` lists analysis scopes
        (``visitor_specific``, ``resident_specific``,
        ``security_specific``, ``estate_wide``) with the averaged scope
        score and nested sub-factors.

        Each spider point, factor, and sub-factor includes
        ``normal_value`` (sample mean), ``scale`` (max value of that
        feature or scope score across *all* predictions in the window,
        including anomalous), and ``percentage``
        (``normal_value / scale * 100``).

    Arguments:
        estate_id: Estate to summarise.
        from_date: Inclusive lower bound on prediction time.
        to_date: Inclusive upper bound on prediction time.

    Returns:
        ``demographic``, ``evidence_summary``, and ``anomaly_overview``.

    Raises:
        HTTPException: 401 if unauthenticated; 404 if the estate does
            not exist; 502 if db-service is unreachable or errors.
    """
    logger.debug(
        "result-page overview caller_id=%s estate_id=%s",
        current_user.get("id"),
        estate_id,
    )
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # counts + 30% normal_sample from db-service
            data = await fetch_overview(
                client,
                settings,
                estate_id=estate_id,
                from_date=from_date,
                to_date=to_date,
            )
        except ResultPageError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
    # maps db counts → demographic / evidence_summary;
    # averages normal_sample → anomaly_overview
    return overview_from_db_payload(data)


@router.get(
    "/predictions",
    response_model=PredictionListResponse,
)
async def list_result_page_predictions(
    estate_id: UUID,
    severity: list[Severity] | None = Query(default=None),
    gender: list[str] | None = Query(default=None),
    user_type: list[UserType] | None = Query(default=None),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1),
    current_user: dict = Depends(get_current_user),
) -> PredictionListResponse:
    """
    List prediction rows for an estate, newest first by default.

    Requires a bearer token. Rows come from db-service
    ``predictionresult`` joined to visitor or resident logs. Repeat
    ``severity``, ``gender``, and ``user_type`` to OR multiple values
    within that category; omitted categories are unfiltered. Categories
    AND with each other.

    Severity is derived from ``final_score``: low < 0.5, medium 0.5 to
    0.8, high >= 0.8. ``user_type=resident`` is role resident, admin, or
    primary_admin (not security). ``gender`` matches visitor-log gender
    for guests and user-profile gender for residents.

    Arguments:
        estate_id: Estate to list.
        severity: One or more of low, medium, high.
        gender: One or more of male, female, prefer_not_to_say.
        user_type: One or more of guest, resident.
        sort_order: Sort by prediction time; default desc.
        from_date: Inclusive lower bound on prediction time.
        to_date: Inclusive upper bound on prediction time.
        page: 1-based page number.
        limit: Page size.

    Returns:
        Paginated ``items`` plus ``total``, ``page``, ``limit``, and
        ``sort_order``. Each item includes id, created_at,
        prediction_type, user_type, gender, display_name, final_score,
        is_anomalous, severity, and anomaly_type.

    Raises:
        HTTPException: 401 if unauthenticated; 502 if db-service is
            unreachable or errors.
    """
    logger.debug(
        "result-page predictions caller_id=%s estate_id=%s",
        current_user.get("id"),
        estate_id,
    )
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            data = await fetch_predictions(
                client,
                settings,
                estate_id=estate_id,
                severity=([s.value for s in severity] if severity else None),
                gender=gender,
                user_type=(
                    [u.value for u in user_type] if user_type else None
                ),
                sort_order=sort_order,
                from_date=from_date,
                to_date=to_date,
                page=page,
                limit=limit,
            )
        except ResultPageError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
    return PredictionListResponse(
        items=data.get("items") or [],
        total=int(data.get("total") or 0),
        page=int(data.get("page") or page),
        limit=int(data.get("limit") or limit),
        sort_order=sort_order,
    )
