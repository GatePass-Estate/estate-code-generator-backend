"""HTTP routes for the incident-report summary result page."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.exceptions import EntitlementDeniedError, ResultPageError
from app.domain.incident_category import IncidentCategory, drop_all_filter
from app.models.incident_resultpage import (
    IncidentListResponse,
    IncidentOverviewResponse,
    IncidentSummaryResponse,
    ReporterUserType,
)
from app.services.incident_resultpage import IncidentResultPageService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service() -> IncidentResultPageService:
    """
    Build a result-page service for the current request.

    Returns:
        A new ``IncidentResultPageService`` bound to default settings.
    """
    return IncidentResultPageService()


def _require_estate_membership(current_user: dict, estate_id: UUID) -> None:
    """
    Reject callers whose JWT estate does not match ``estate_id``.

    Membership is an endpoint-layer concern (RBAC will follow later).
    """
    user_estate_id = current_user.get("estate_id")
    if user_estate_id is None or str(user_estate_id) != str(estate_id):
        raise HTTPException(
            status_code=403,
            detail="User does not belong to this estate.",
        )


def _to_http(exc: ResultPageError | EntitlementDeniedError) -> HTTPException:
    """
    Map a domain error onto an HTTPException.

    Arguments:
        exc: Service-layer error with ``status_code`` and ``message``.

    Returns:
        An HTTPException with the same status and detail.
    """
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _parse_enum_filter(
    values: list[str] | None,
    enum_cls: type[IncidentCategory] | type[ReporterUserType],
    label: str,
) -> list[str] | None:
    """
    Drop ``all``, then require each remaining value to be in ``enum_cls``.

    Arguments:
        values: Raw query values from FastAPI.
        enum_cls: Allowed set after ``all`` is removed.
        label: Field name used in the 422 detail.

    Returns:
        Lowercased allowed values, or ``None`` when unfiltered.

    Raises:
        HTTPException: 422 if a remaining value is not in
            ``enum_cls``.
    """
    remaining = drop_all_filter(values)
    if remaining is None:
        return None
    parsed: list[str] = []
    allowed = {item.value for item in enum_cls}
    for value in remaining:
        if value not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid {label}: {value}.",
            )
        parsed.append(value)
    return parsed


@router.get(
    "/overview",
    response_model=IncidentOverviewResponse,
)
async def get_result_page_overview(
    estate_id: UUID,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    current_user: dict = Depends(get_current_user),
    service: IncidentResultPageService = Depends(get_service),
) -> IncidentOverviewResponse:
    """
    Build the incident result-page overview for one estate.

    Returns demographic counts and exploratory statistics for the
    requested date window. Requires a bearer token. Estate identity
    and reporter-role counts come from db-service; category EDA and
    the trends sentence are computed here.

    Date window (``from_date``, ``to_date``) filters incident rows by
    ``created_at``. Omit both dates to include all retained reports.

    Demographic
        ``estate_name``, ``state``, and ``country`` come from the estate
        record. ``total_reports`` is the incident row count in the
        window. ``ratio`` is resident / security counts and each
        group's percentage of resident + security. Resident covers
        every reporter role except security, guest, and root.

    EDA
        ``stats`` is the existing cohort EDA (category distribution,
        field quality, occurred-at range). ``categories`` ranks only
        the fixed taxonomy labels by count: ``top_1`` … ``top_5`` are
        separate fields; remaining labels sit under
        ``other_categories`` ordered by count descending. Custom
        category text is not ranked. Each category includes peak time
        (morning, afternoon, evening/night), count, percentage of all
        reports, and two sample snippets. ``trends_detected`` is a
        formatted sentence from those figures.

    Cache
        ``has_tier1_summary`` / ``has_tier2_summary`` are true when
        that payload is already stored for this estate and date
        window (in-house topic modelling / LLM).

    Arguments:
        estate_id: Estate to summarise.
        from_date: Inclusive lower bound on incident created_at.
        to_date: Inclusive upper bound on incident created_at.

    Returns:
        ``demographic``, ``eda``, and the two cache flags.

    Raises:
        HTTPException: 401 if unauthenticated; 403 if the caller does
            not belong to the estate or has no result-page grant; 404
            if the estate does not exist; 502 if db-service is
            unreachable or errors.
    """
    _require_estate_membership(current_user, estate_id)
    logger.debug(
        "incident result-page overview caller_id=%s estate_id=%s",
        current_user.get("id"),
        estate_id,
    )
    try:
        return await service.get_overview(
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
        )
    except (ResultPageError, EntitlementDeniedError) as e:
        raise _to_http(e) from e


@router.get(
    "/reports",
    response_model=IncidentListResponse,
)
async def list_result_page_reports(
    estate_id: UUID,
    category: list[str] | None = Query(default=None),
    user_type: list[str] | None = Query(default=None),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1),
    current_user: dict = Depends(get_current_user),
    service: IncidentResultPageService = Depends(get_service),
) -> IncidentListResponse:
    """
    List incident reports for an estate, newest first.

    Requires a bearer token. Repeat ``category`` and ``user_type`` to
    OR multiple values within that filter; omitted filters are
    unfiltered. ``category=all`` or ``user_type=all`` is the same as
    omitting that filter (every type). Filters AND with each other.

    ``user_type=resident`` is every reporter role except security,
    guest, and root. ``user_type=security`` is security only.

    Arguments:
        estate_id: Estate to list.
        category: Taxonomy values, or ``all`` for every category.
        user_type: ``resident``, ``security``, or ``all``.
        from_date: Inclusive lower bound on created_at.
        to_date: Inclusive upper bound on created_at.
        page: 1-based page number.
        limit: Page size.

    Returns:
        Paginated ``items`` plus ``total``, ``page``, and ``limit``.
        Each item includes id, timestamps, title, categories,
        narrative, and ``reporter_user_type``.

    Raises:
        HTTPException: 401 if unauthenticated; 403 if the caller does
            not belong to the estate or has no result-page grant; 502
            if db-service is unreachable or errors.
    """
    _require_estate_membership(current_user, estate_id)
    logger.debug(
        "incident result-page reports caller_id=%s estate_id=%s",
        current_user.get("id"),
        estate_id,
    )
    try:
        return await service.list_reports(
            estate_id=estate_id,
            categories=_parse_enum_filter(
                category, IncidentCategory, "category"
            ),
            user_types=_parse_enum_filter(
                user_type, ReporterUserType, "user_type"
            ),
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        )
    except (ResultPageError, EntitlementDeniedError) as e:
        raise _to_http(e) from e


@router.get(
    "/summary",
    response_model=IncidentSummaryResponse,
)
async def get_result_page_summary(
    estate_id: UUID,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    current_user: dict = Depends(get_current_user),
    service: IncidentResultPageService = Depends(get_service),
) -> IncidentSummaryResponse:
    """
    Entitlement-gated topic-modelling and LLM summary for one window.

    The cohort is every retained incident in the selected date range
    (not a row-count cap). Always re-checks grants so a downgraded
    subscription withholds a previously generated report. Cached
    ``ai_response`` rows keyed by estate + date window are reused when
    present; otherwise the missing entitled tier is generated and stored.

    ``incident_summary_basic`` unlocks this result page without AI
    summaries. ``incident_summary_basic_tier2`` is in-house topic
    modelling. ``incident_summary_basic_tier3`` adds the LLM
    narrative and includes tier 2. Both summary payloads carry the
    same category EDA.

    Arguments:
        estate_id: Estate used for the AI feature check and cache key.
        from_date: Inclusive lower bound on created_at (part of the key).
        to_date: Inclusive upper bound on created_at (part of the key).

    Returns:
        Entitled tier, cache flag, and the granted summary payloads.

    Raises:
        HTTPException: 401 if unauthenticated; 403 if the caller does
            not belong to the estate or no summary grant is allowed;
            502 on downstream errors.
    """
    _require_estate_membership(current_user, estate_id)
    logger.debug(
        "incident result-page summary caller_id=%s estate_id=%s",
        current_user.get("id"),
        estate_id,
    )
    try:
        return await service.get_summary(
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
        )
    except (ResultPageError, EntitlementDeniedError) as e:
        raise _to_http(e) from e
