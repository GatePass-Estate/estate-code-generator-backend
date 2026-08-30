"""HTTP routes for the spatial-anomaly result page."""

import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.exceptions import EntitlementDeniedError, ResultPageError
from app.integrations.db_service_prediction_result import (
    fetch_case_demographic,
    fetch_case_detail,
    fetch_case_history,
    fetch_overview,
    fetch_predictions,
    patch_ai_summary,
)
from app.integrations.revenue_service import (
    ANOMALY_SUMMARY_TIER2_KEY,
    ANOMALY_SUMMARY_TIER3_KEY,
    is_ai_feature_allowed,
)
from app.models.spatial_anomaly_resultpage import (
    CaseDemographic,
    CaseHistoryItem,
    CaseHistoryResponse,
    CaseResultsResponse,
    CaseSummaryResponse,
    InhouseSummary,
    LlmSummary,
    PredictionListResponse,
    ResultPageOverviewResponse,
    Severity,
    UserType,
)
from app.pipeline.spatial_anomaly_case_summary import (
    build_inhouse_summary,
    summarize_case_with_llm,
)
from app.pipeline.spatial_anomaly_resultpage import (
    case_results_from_db_payload,
    overview_from_db_payload,
)

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
        is_anomalous, severity, anomaly_type, and flags
        ``has_tier1_summary`` / ``has_tier2_summary`` (cache present,
        not the summary body).

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


@router.get(
    "/cases/{prediction_id}/demographic",
    response_model=CaseDemographic,
)
async def get_case_demographic(
    prediction_id: UUID,
    estate_id: UUID,
    display_name: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    current_user: dict = Depends(get_current_user),
) -> CaseDemographic:
    """
    Person-level demographic for a selected prediction case.

    Returns name, user type, total log entries in the date window,
    average entries per week, resident ``user_id`` for the display
    picture (null for guests), and cache flags for each summary tier.

    Arguments:
        prediction_id: Selected prediction from the list.
        estate_id: Estate that owns the visitor or resident log.
        display_name: Optional name override; defaults to the joined log.
        from_date: Inclusive lower bound on log timestamps.
        to_date: Inclusive upper bound on log timestamps.

    Returns:
        ``CaseDemographic`` for the selected person, including
        ``has_tier1_summary`` / ``has_tier2_summary`` (cache present,
        not the summary body).

    Raises:
        HTTPException: 401 if unauthenticated; 404 if the prediction is
            missing; 502 if db-service is unreachable or errors.
    """
    logger.debug(
        "result-page case demographic caller_id=%s prediction_id=%s",
        current_user.get("id"),
        prediction_id,
    )
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            data = await fetch_case_demographic(
                client,
                settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                display_name=display_name,
                from_date=from_date,
                to_date=to_date,
            )
        except ResultPageError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
    return CaseDemographic(
        prediction_id=str(data.get("prediction_id") or prediction_id),
        display_name=data.get("display_name"),
        user_type=UserType(data.get("user_type") or UserType.GUEST),
        user_id=data.get("user_id"),
        total_entries=int(data.get("total_entries") or 0),
        average_entry_per_week=float(
            data.get("average_entry_per_week") or 0.0
        ),
        has_tier1_summary=bool(data.get("has_tier1_summary")),
        has_tier2_summary=bool(data.get("has_tier2_summary")),
    )


@router.get(
    "/cases/{prediction_id}/history",
    response_model=CaseHistoryResponse,
)
async def get_case_history(
    prediction_id: UUID,
    estate_id: UUID,
    display_name: str | None = None,
    history_limit: int = Query(default=5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
) -> CaseHistoryResponse:
    """
    Five most recent predictions for the same visitor or resident name.

    The selected instance is the newest row. Each item includes
    validation timestamp, validated code, and severity.

    Arguments:
        prediction_id: Selected prediction (most recent in the list).
        estate_id: Estate that owns the visitor or resident log.
        display_name: Optional name override; defaults to the joined log.
        history_limit: Max rows; default 5.

    Returns:
        History items newest-first, selected case first.

    Raises:
        HTTPException: 401 if unauthenticated; 404 if the prediction is
            missing; 502 if db-service is unreachable or errors.
    """
    logger.debug(
        "result-page case history caller_id=%s prediction_id=%s",
        current_user.get("id"),
        prediction_id,
    )
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            data = await fetch_case_history(
                client,
                settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                display_name=display_name,
                history_limit=history_limit,
            )
        except ResultPageError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
    items = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        items.append(CaseHistoryItem(**raw))
    return CaseHistoryResponse(items=items)


@router.get(
    "/cases/{prediction_id}/summary",
    response_model=CaseSummaryResponse,
)
async def get_case_summary(
    prediction_id: UUID,
    estate_id: UUID,
    current_user: dict = Depends(get_current_user),
) -> CaseSummaryResponse:
    """
    Entitlement-gated in-house and/or LLM summary for one case.

    Always re-checks the estate AI grant so a downgraded subscription
    withholds a previously generated tier. Cached ``ai_summary.tier1`` /
    ``tier2`` on the prediction row are reused when present; otherwise
    the missing tier is generated and stored.

    Tier 2 includes tier 1. The list endpoint never returns the summary
    body, only ``has_tier1_summary`` / ``has_tier2_summary`` flags.

    Arguments:
        prediction_id: Selected prediction row.
        estate_id: Estate used for the AI feature check.

    Returns:
        Entitled tier, cache flag, and the summaries that grant allows.

    Raises:
        HTTPException: 401 if unauthenticated; 403 if neither summary
            grant is allowed; 404 if the prediction is missing; 502 on
            downstream errors.
    """
    logger.debug(
        "result-page case summary caller_id=%s prediction_id=%s",
        current_user.get("id"),
        prediction_id,
    )
    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            # 1. Re-check grants every call. Tier3 implies both; else
            #    tier2 (in-house only); neither → 403.
            tier2_ok = await is_ai_feature_allowed(
                client,
                settings,
                estate_id=estate_id,
                feature_key=ANOMALY_SUMMARY_TIER3_KEY,
            )
            tier1_ok = tier2_ok or await is_ai_feature_allowed(
                client,
                settings,
                estate_id=estate_id,
                feature_key=ANOMALY_SUMMARY_TIER2_KEY,
            )
            if not tier1_ok:
                raise HTTPException(
                    status_code=403,
                    detail=("Estate is not entitled to anomaly case summary."),
                )
            data = await fetch_case_detail(
                client,
                settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                from_date=None,
                to_date=None,
            )
            cache = data.get("ai_summary") or {}
            if not isinstance(cache, dict):
                cache = {}
            result = data.get("result") or {}
            if not isinstance(result, dict):
                result = {}

            # 2. Reuse cached tier1 / tier2 when present; invalid JSON
            #    is treated as missing.
            cached_t1 = cache.get("tier1")
            cached_t2 = cache.get("tier2")
            inhouse: InhouseSummary | None = None
            llm: LlmSummary | None = None
            generated = False
            if isinstance(cached_t1, dict) and cached_t1:
                try:
                    inhouse = InhouseSummary.model_validate(cached_t1)
                except ValidationError:
                    inhouse = None
            if isinstance(cached_t2, dict) and cached_t2:
                try:
                    llm = LlmSummary.model_validate(cached_t2)
                except ValidationError:
                    llm = None

            # 3. Generate missing tiers, persist, then withhold LLM if
            #    the estate is only entitled to in-house.
            patch_t1 = None
            patch_t2 = None
            if inhouse is None:
                inhouse = build_inhouse_summary(result)
                patch_t1 = inhouse.model_dump()
                generated = True
            if tier2_ok and llm is None:
                llm, _used = await summarize_case_with_llm(
                    client=client,
                    settings=settings,
                    payload=result,
                    inhouse=inhouse,
                )
                patch_t2 = llm.model_dump()
                generated = True
            if patch_t1 is not None or patch_t2 is not None:
                await patch_ai_summary(
                    client,
                    settings,
                    prediction_id=prediction_id,
                    tier1=patch_t1,
                    tier2=patch_t2,
                )
        except ResultPageError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
        except EntitlementDeniedError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
    return CaseSummaryResponse(
        entitled_tier="tier2" if tier2_ok else "tier1",
        from_cache=not generated,
        tier1=inhouse,
        tier2=llm if tier2_ok else None,
    )


@router.get(
    "/cases/{prediction_id}/results",
    response_model=CaseResultsResponse,
)
async def get_case_results(
    prediction_id: UUID,
    estate_id: UUID,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    current_user: dict = Depends(get_current_user),
) -> CaseResultsResponse:
    """
    Spider plot and contributing factors for the selected prediction.

    Expected-normal values reuse the first-level 30% non-anomalous
    sample. The spider plot also includes this instance's value, the
    period max (scale), and percentages of both versus that max.
    Contributing factors include instance value, max, and percentage.
    Which sections appear follows ``scopes_for_anomaly_type`` for this
    prediction (visitor: all four; resident: no visitor-specific).

    Arguments:
        prediction_id: Selected prediction row.
        estate_id: Estate that owns the visitor or resident log.
        from_date: Inclusive lower bound for sample and max maps.
        to_date: Inclusive upper bound for sample and max maps.

    Returns:
        Score, severity, and the case anomaly overview.

    Raises:
        HTTPException: 401 if unauthenticated; 404 if the prediction is
            missing; 502 if db-service is unreachable or errors.
    """
    logger.debug(
        "result-page case results caller_id=%s prediction_id=%s",
        current_user.get("id"),
        prediction_id,
    )
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            data = await fetch_case_detail(
                client,
                settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                from_date=from_date,
                to_date=to_date,
            )
        except ResultPageError as e:
            raise HTTPException(
                status_code=e.status_code, detail=e.message
            ) from e
    return case_results_from_db_payload(data, prediction_id=str(prediction_id))
