"""Business logic for the incident-report summary result page."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from gatepass_entitlement import (
    INCIDENT_REPORT_SUMMARY_TIER_1_KEY,
    resolve_incident_entitlements,
)
from pydantic import ValidationError

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.exceptions import (
    EntitlementDeniedError,
    IncidentReportError,
    ResultPageError,
)
from app.domain.ai_summary import incident_lookup_key
from app.integrations.db_service_ai_summary import (
    fetch_ai_summary,
    upsert_ai_summary,
)
from app.integrations.db_service_incident_reports import (
    load_incident_reports_for_estate,
)
from app.integrations.db_service_incident_resultpage import (
    fetch_incident_overview,
    fetch_incident_reports,
)
from app.models.incident_resultpage import (
    IncidentInhouseSummary,
    IncidentListItem,
    IncidentListResponse,
    IncidentLlmSummary,
    IncidentOverviewResponse,
    IncidentSummaryResponse,
)
from app.pipeline.incident_eda import build_incident_eda
from app.pipeline.incident_llm_summarizer import summarize_incidents_with_llm
from app.pipeline.incident_resultpage import (
    attach_category_eda,
    build_inhouse_incident_summary,
    overview_from_parts,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0)
_SUMMARY_TIMEOUT = httpx.Timeout(120.0)


def _parse_cached(model: type, raw: Any):
    """
    Validate a stored tier payload, or return ``None`` if unusable.

    Empty dicts and schema mismatches are treated as a cache miss so
    the caller can regenerate that tier.

    Arguments:
        model: Pydantic model for the stored tier.
        raw: Value of ``ai_summary.tier1`` or ``ai_summary.tier2``.

    Returns:
        A validated instance, or ``None``.
    """
    if isinstance(raw, dict) and raw:
        try:
            return model.model_validate(raw)
        except ValidationError:
            return None
    return None


def _tier_present(raw: Any, key: str) -> bool:
    """
    Return whether ``raw[key]`` holds a non-empty cached report.

    Arguments:
        raw: The ``ai_summary`` JSON object, or anything else.
        key: ``tier1`` or ``tier2``.

    Returns:
        ``False`` when ``raw`` is not a dict or the value is missing,
        ``None``, ``""``, or ``{}``.
    """
    if not isinstance(raw, dict):
        return False
    value = raw.get(key)
    return not (value is None or value == "" or value == {})


def _cache_tier_flags(cache: dict[str, Any] | None) -> tuple[bool, bool]:
    """
    Read stored tier-1 / tier-2 presence from an ``ai_response`` row.

    Prefers db-service ``has_tier*_summary`` flags when present;
    otherwise inspects ``ai_summary.tier1`` / ``tier2``.

    Arguments:
        cache: GET ``/ai-features/ai-response`` body, or ``None``.

    Returns:
        ``(has_tier1_summary, has_tier2_summary)``.
    """
    if not isinstance(cache, dict):
        return False, False
    payload = cache.get("ai_summary")
    if "has_tier1_summary" in cache or "has_tier2_summary" in cache:
        return (
            bool(cache.get("has_tier1_summary")),
            bool(cache.get("has_tier2_summary")),
        )
    return _tier_present(payload, "tier1"), _tier_present(payload, "tier2")


def _coerce_llm_lists(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize chat list fields that sometimes arrive as scalars.

    Arguments:
        raw: Parsed LLM JSON before ``IncidentLlmSummary`` validation.

    Returns:
        A shallow copy with ``key_patterns`` and
        ``recommended_actions`` forced to lists.
    """
    out = dict(raw)
    for key in ("key_patterns", "recommended_actions"):
        value = out.get(key)
        if isinstance(value, str):
            out[key] = [value]
        elif value is None:
            out[key] = []
        elif not isinstance(value, list):
            out[key] = [str(value)]
    return out


class IncidentResultPageService:
    """Fetch, map, and entitlement-gate incident result-page payloads."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Bind settings used for db-service and revenue-service calls."""
        self.settings = settings or default_settings

    async def get_overview(
        self,
        *,
        estate_id: UUID,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> IncidentOverviewResponse:
        """
        Build demographics, category EDA, trends, and cache flags.

        Requires any incident result-page grant (basic, tier 2, or
        tier 3). Does not generate summaries; it only reports whether
        each tier is already stored for this estate and date window.

        Arguments:
            estate_id: Estate whose incidents are summarised.
            from_date: Inclusive ``created_at`` lower bound, or open.
            to_date: Inclusive ``created_at`` upper bound, or open.

        Returns:
            Estate identity, reporter-role ratio, ranked fixed
            categories, a trends sentence, and
            ``has_tier1_summary`` / ``has_tier2_summary``.

        Raises:
            EntitlementDeniedError: Estate has no result-page grant.
            ResultPageError: db-service failed or the estate is
                missing.
        """
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            # 1. Gate the page. Summary grants are unused here.
            (
                page_ok,
                _inhouse_ok,
                _llm_ok,
            ) = await resolve_incident_entitlements(
                self.settings.REVENUE_SERVICE_URL,
                estate_id=estate_id,
                client=client,
            )
            if not page_ok:
                raise EntitlementDeniedError(
                    "Estate is not entitled to the incident result page.",
                    status_code=403,
                )
            # 2. Estate identity and resident / security counts.
            db_overview = await fetch_incident_overview(
                client,
                self.settings,
                estate_id=estate_id,
                from_date=from_date,
                to_date=to_date,
            )
            # 3. Full window of rows for category EDA and trends.
            try:
                records = await load_incident_reports_for_estate(
                    client,
                    self.settings,
                    estate_id=estate_id,
                    from_date=from_date,
                    to_date=to_date,
                )
            except IncidentReportError as exc:
                raise ResultPageError(
                    exc.message, status_code=exc.status_code
                ) from exc
            # 4. Same cache key as /summary; flags only, no generate.
            cache = await fetch_ai_summary(
                client,
                self.settings,
                feature_key=INCIDENT_REPORT_SUMMARY_TIER_1_KEY,
                lookup_key=incident_lookup_key(estate_id, from_date, to_date),
            )
            has_tier1, has_tier2 = _cache_tier_flags(cache)
        return overview_from_parts(
            db_overview=db_overview,
            records=records,
            has_tier1_summary=has_tier1,
            has_tier2_summary=has_tier2,
        )

    async def list_reports(
        self,
        *,
        estate_id: UUID,
        categories: list[str] | None,
        user_types: list[str] | None,
        from_date: datetime | None,
        to_date: datetime | None,
        page: int,
        limit: int,
    ) -> IncidentListResponse:
        """
        List estate incidents for the result-page table.

        ``categories`` and ``user_types`` are already normalized
        (``all`` stripped). ``None`` means that filter is omitted.

        Arguments:
            estate_id: Estate to list.
            categories: Fixed taxonomy values, or ``None`` for all.
            user_types: ``resident`` and/or ``security``, or ``None``.
            from_date: Inclusive ``created_at`` lower bound, or open.
            to_date: Inclusive ``created_at`` upper bound, or open.
            page: 1-based page number.
            limit: Page size.

        Returns:
            Paginated list items plus ``total``, ``page``, and
            ``limit``.

        Raises:
            EntitlementDeniedError: Estate has no result-page grant.
            ResultPageError: db-service failed.
        """
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            (
                page_ok,
                _inhouse_ok,
                _llm_ok,
            ) = await resolve_incident_entitlements(
                self.settings.REVENUE_SERVICE_URL,
                estate_id=estate_id,
                client=client,
            )
            if not page_ok:
                raise EntitlementDeniedError(
                    "Estate is not entitled to the incident result page.",
                    status_code=403,
                )
            data = await fetch_incident_reports(
                client,
                self.settings,
                estate_id=estate_id,
                categories=categories,
                user_types=user_types,
                from_date=from_date,
                to_date=to_date,
                page=page,
                limit=limit,
            )
        items: list[IncidentListItem] = []
        for raw in data.get("items") or []:
            if not isinstance(raw, dict):
                continue
            items.append(IncidentListItem.model_validate(raw))
        return IncidentListResponse(
            items=items,
            total=int(data.get("total") or 0),
            page=int(data.get("page") or page),
            limit=int(data.get("limit") or limit),
        )

    async def get_summary(
        self,
        *,
        estate_id: UUID,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> IncidentSummaryResponse:
        """
        Load or generate entitled summaries for one estate window.

        Catalog keys and stored JSON keys differ:

        - ``incident_report_summary_tier_2`` unlocks in-house topics,
          stored as ``ai_summary.tier1``.
        - ``incident_report_summary_tier_3`` unlocks the LLM narrative,
          stored as ``ai_summary.tier2``, and includes tier 2.

        Cache key is ``{estate_id}:{from}:{to}`` (``open`` if a bound
        is omitted). The upsert writes only the tiers passed in, so
        a later LLM grant can add ``tier2`` without regenerating
        ``tier1``. Grants are re-checked every call: a downgrade
        withholds the LLM body even if it is still in cache.

        The cohort is every retained incident in the window (no row
        cap). Rows are loaded only when an entitled tier is missing.

        Arguments:
            estate_id: Estate used for grants and the cache key.
            from_date: Inclusive ``created_at`` lower bound, or open.
            to_date: Inclusive ``created_at`` upper bound, or open.

        Returns:
            ``entitled_tier`` (``tier1`` or ``tier2``), ``from_cache``,
            the in-house payload, and the LLM payload when granted.

        Raises:
            EntitlementDeniedError: No in-house (catalog tier 2)
                grant.
            ResultPageError: Incident load or cache I/O failed.
        """
        async with httpx.AsyncClient(timeout=_SUMMARY_TIMEOUT) as client:
            # 1. Catalog tier 2 is required; catalog tier 3 is optional.
            _page_ok, inhouse_ok, llm_ok = await resolve_incident_entitlements(
                self.settings.REVENUE_SERVICE_URL,
                estate_id=estate_id,
                client=client,
            )
            if not inhouse_ok:
                raise EntitlementDeniedError(
                    "Estate is not entitled to incident summary.",
                    status_code=403,
                )
            # 2. One cache row per estate + date window.
            lookup_key = incident_lookup_key(estate_id, from_date, to_date)
            # 3. Read the existing JSON (404 becomes an empty dict).
            cache = await fetch_ai_summary(
                client,
                self.settings,
                feature_key=INCIDENT_REPORT_SUMMARY_TIER_1_KEY,
                lookup_key=lookup_key,
            )
            if not isinstance(cache, dict):
                cache = {}
            payload = cache.get("ai_summary") or {}
            if not isinstance(payload, dict):
                payload = {}
            # 4. Invalid stored JSON is a miss so that tier can rebuild.
            inhouse = _parse_cached(
                IncidentInhouseSummary, payload.get("tier1")
            )
            llm = _parse_cached(IncidentLlmSummary, payload.get("tier2"))
            generated = False
            patch_t1 = None
            patch_t2 = None
            records: list[dict[str, Any]] | None = None
            # 5. Fetch rows only if an entitled tier still needs work.
            need_records = inhouse is None or (llm_ok and llm is None)
            if need_records:
                try:
                    records = await load_incident_reports_for_estate(
                        client,
                        self.settings,
                        estate_id=estate_id,
                        from_date=from_date,
                        to_date=to_date,
                    )
                except IncidentReportError as exc:
                    raise ResultPageError(
                        exc.message, status_code=exc.status_code
                    ) from exc
            # 6. In-house topics: generate only when cache missed.
            if inhouse is None:
                inhouse = build_inhouse_incident_summary(records or [])
                patch_t1 = inhouse.model_dump()
                generated = True
            # 7. LLM: only if catalog tier 3 is granted and missing.
            if llm_ok and llm is None:
                eda = build_incident_eda(records or [])
                raw, _model, _used = await summarize_incidents_with_llm(
                    client=client,
                    settings=self.settings,
                    records=records or [],
                    eda=eda,
                )
                llm = IncidentLlmSummary.model_validate(_coerce_llm_lists(raw))
                llm = attach_category_eda(llm, inhouse.category_eda)
                patch_t2 = llm.model_dump()
                generated = True
            # 8. Merge only supplied keys; omitted tiers stay stored.
            if patch_t1 is not None or patch_t2 is not None:
                await upsert_ai_summary(
                    client,
                    self.settings,
                    feature_key=INCIDENT_REPORT_SUMMARY_TIER_1_KEY,
                    lookup_key=lookup_key,
                    estate_id=estate_id,
                    from_date=from_date,
                    to_date=to_date,
                    tier1=patch_t1,
                    tier2=patch_t2,
                )
        # 9. Withhold the LLM body when the estate is not entitled.
        return IncidentSummaryResponse(
            entitled_tier="tier2" if llm_ok else "tier1",
            from_cache=not generated,
            tier1=inhouse,
            tier2=llm if llm_ok else None,
        )
