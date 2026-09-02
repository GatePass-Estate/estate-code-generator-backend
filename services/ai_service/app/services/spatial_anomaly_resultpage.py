"""Business logic for the spatial-anomaly result page."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.config import Settings, settings as default_settings
from app.core.exceptions import EntitlementDeniedError
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

_DEFAULT_TIMEOUT = httpx.Timeout(30.0)
_SUMMARY_TIMEOUT = httpx.Timeout(60.0)


def _parse_cached(model: type, raw: Any):
    """Return a validated model from a cache dict, or None if unusable."""
    if isinstance(raw, dict) and raw:
        try:
            return model.model_validate(raw)
        except ValidationError:
            return None
    return None


class SpatialAnomalyResultPageService:
    """Fetch, map, and entitlement-gate result-page payloads."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Bind settings used for db-service and revenue-service calls."""
        self.settings = settings or default_settings

    async def get_overview(
        self,
        *,
        estate_id: UUID,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> ResultPageOverviewResponse:
        """Load overview counts and build demographic / anomaly overview."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            data = await fetch_overview(
                client,
                self.settings,
                estate_id=estate_id,
                from_date=from_date,
                to_date=to_date,
            )
        return overview_from_db_payload(data)

    async def list_predictions(
        self,
        *,
        estate_id: UUID,
        severity: list[Severity] | None,
        gender: list[str] | None,
        user_type: list[UserType] | None,
        sort_order: Literal["asc", "desc"],
        from_date: datetime | None,
        to_date: datetime | None,
        page: int,
        limit: int,
    ) -> PredictionListResponse:
        """List prediction rows for an estate, mapped onto the list schema."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            data = await fetch_predictions(
                client,
                self.settings,
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
        return PredictionListResponse(
            items=data.get("items") or [],
            total=int(data.get("total") or 0),
            page=int(data.get("page") or page),
            limit=int(data.get("limit") or limit),
            sort_order=sort_order,
        )

    async def get_case_demographic(
        self,
        *,
        prediction_id: UUID,
        estate_id: UUID,
        display_name: str | None,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> CaseDemographic:
        """Map db-service case demographic onto the response model."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            data = await fetch_case_demographic(
                client,
                self.settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                display_name=display_name,
                from_date=from_date,
                to_date=to_date,
            )
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

    async def get_case_history(
        self,
        *,
        prediction_id: UUID,
        estate_id: UUID,
        display_name: str | None,
        history_limit: int,
    ) -> CaseHistoryResponse:
        """Map db-service case history rows onto the response model."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            data = await fetch_case_history(
                client,
                self.settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                display_name=display_name,
                history_limit=history_limit,
            )
        items: list[CaseHistoryItem] = []
        for raw in data.get("items") or []:
            if not isinstance(raw, dict):
                continue
            items.append(CaseHistoryItem(**raw))
        return CaseHistoryResponse(items=items)

    async def get_case_results(
        self,
        *,
        prediction_id: UUID,
        estate_id: UUID,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> CaseResultsResponse:
        """Load a case payload and overlay instance values on normal data."""
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            data = await fetch_case_detail(
                client,
                self.settings,
                prediction_id=prediction_id,
                estate_id=estate_id,
                from_date=from_date,
                to_date=to_date,
            )
        return case_results_from_db_payload(
            data, prediction_id=str(prediction_id)
        )

    async def get_case_summary(
        self,
        *,
        prediction_id: UUID,
        estate_id: UUID,
    ) -> CaseSummaryResponse:
        """
        Entitlement-gated in-house and/or LLM summary for one case.

        Re-checks the estate AI grant so a downgraded subscription
        withholds a previously generated tier. Cached ``ai_summary.tier1``
        / ``tier2`` are reused when present; otherwise the missing tier
        is generated and stored.
        """
        async with httpx.AsyncClient(timeout=_SUMMARY_TIMEOUT) as client:
            # Re-check grants every call. Tier3 implies both; else
            # tier2 (in-house only); neither → 403.
            tier2_ok = await is_ai_feature_allowed(
                client,
                self.settings,
                estate_id=estate_id,
                feature_key=ANOMALY_SUMMARY_TIER3_KEY,
            )
            tier1_ok = tier2_ok or await is_ai_feature_allowed(
                client,
                self.settings,
                estate_id=estate_id,
                feature_key=ANOMALY_SUMMARY_TIER2_KEY,
            )
            if not tier1_ok:
                raise EntitlementDeniedError(
                    "Estate is not entitled to anomaly case summary.",
                    status_code=403,
                )
            data = await fetch_case_detail(
                client,
                self.settings,
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

            inhouse = _parse_cached(InhouseSummary, cache.get("tier1"))
            llm = _parse_cached(LlmSummary, cache.get("tier2"))
            generated = False
            patch_t1 = None
            patch_t2 = None
            if inhouse is None:
                inhouse = build_inhouse_summary(result)
                patch_t1 = inhouse.model_dump()
                generated = True
            if tier2_ok and llm is None:
                llm, _used = await summarize_case_with_llm(
                    client=client,
                    settings=self.settings,
                    payload=result,
                    inhouse=inhouse,
                )
                patch_t2 = llm.model_dump()
                generated = True
            if patch_t1 is not None or patch_t2 is not None:
                await patch_ai_summary(
                    client,
                    self.settings,
                    prediction_id=prediction_id,
                    tier1=patch_t1,
                    tier2=patch_t2,
                )
        return CaseSummaryResponse(
            entitled_tier="tier2" if tier2_ok else "tier1",
            from_cache=not generated,
            tier1=inhouse,
            tier2=llm if tier2_ok else None,
        )
