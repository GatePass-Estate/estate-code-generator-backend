"""Pull visitor/resident log rows from db-service for spatial anomaly analysis."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from app.core.config import Settings, settings
from app.core.exceptions import LogHistoryError
from app.domain.scopes import AnalysisScope
from app.models.code_validation import CodeValidationPayload
from app.core.spatial_anomaly_trace import trace

logger = logging.getLogger(__name__)

HISTORY_WINDOW_DAYS = 30


@dataclass(frozen=True)
class LogHistorySlices:
    """
    Wrangled log rows for one anchor, fetched **per scope** with scope filters.

    Most scopes use their own db-service search (up to
    ``SPATIAL_SCOPE_HISTORY_LIMIT`` rows ending at the anchor). **Temporal**
    is focal-only — clock/calendar features need no log history. Resident
    anchors skip visitor-scope fetch.

    All list fields are **already passed through** ``wrangle_visit_records``.
    ``focal_record`` remains the raw anchor dict from db-service.
    """

    source: Literal["visitor_log", "resident_log"]
    payload: CodeValidationPayload
    focal_record: dict[str, Any]
    merged_full: list[dict[str, Any]]
    temporal: list[dict[str, Any]]
    estate_wide: list[dict[str, Any]]
    visitor_specific: list[dict[str, Any]]
    resident_specific: list[dict[str, Any]]
    security_specific: list[dict[str, Any]]

    def rows_for_analysis_scope(
        self, scope: AnalysisScope
    ) -> list[dict[str, Any]]:
        """Wrangled rows to pass into feature engineering for ``scope``."""
        mapping: dict[AnalysisScope, list[dict[str, Any]]] = {
            AnalysisScope.TEMPORAL: self.temporal,
            AnalysisScope.ESTATE_WIDE: self.estate_wide,
            AnalysisScope.VISITOR: self.visitor_specific,
            AnalysisScope.RESIDENT: self.resident_specific,
            AnalysisScope.SECURITY: self.security_specific,
        }
        return list(mapping[scope])

    def rows_by_analysis_scope(
        self,
    ) -> dict[AnalysisScope, list[dict[str, Any]]]:
        """All scopes; each value is the wrangled slice for that scope."""
        return {s: self.rows_for_analysis_scope(s) for s in AnalysisScope}

    def rows_for_history_lookup(
        self, scope: AnalysisScope
    ) -> list[dict[str, Any]]:
        """
        Cohort for prior-log feature-store batch lookup when scoring.

        Temporal features are focal-only, but detector history still uses
        stored ``features_temporal`` from the resident cohort.
        """
        if scope == AnalysisScope.TEMPORAL:
            return self.rows_for_analysis_scope(AnalysisScope.RESIDENT)
        return self.rows_for_analysis_scope(scope)


def _db_url(settings: Settings, path: str) -> str:
    """Absolute URL under ``DB_SERVICE_URL`` for a db-service path segment."""
    base = settings.DB_SERVICE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _format_query_datetime(dt: datetime) -> str:
    """UTC ISO string safe for query params (avoid ambiguous ``+``)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _record_event_time_or_none(rec: dict[str, Any]) -> datetime | None:
    """Parse primary event time (visit / access / created) or return ``None``."""
    for key in ("visit_time", "access_time", "created_at"):
        raw = rec.get(key)
        if raw is None:
            continue
        if isinstance(raw, datetime):
            ts = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
            return ts
        if isinstance(raw, str):
            v = raw.replace("Z", "+00:00")
            try:
                ts = datetime.fromisoformat(v)
            except ValueError:
                continue
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return None


def _event_time_for_sort(rec: dict[str, Any]) -> datetime:
    """Primary event timestamp for ordering visitor or resident log rows."""
    ts = _record_event_time_or_none(rec)
    if ts is not None:
        return ts
    return datetime.min.replace(tzinfo=timezone.utc)


def _history_search_end_from_anchor(anchor: dict[str, Any]) -> datetime:
    """
    Upper bound for scope history searches (inclusive ``to_date``).

    Uses the later of event time and ``created_at`` so a just-inserted anchor
    row is not excluded when validation timestamps precede ``created_at``.
    """
    end = _record_event_time_or_none(anchor)
    created = None
    raw_created = anchor.get("created_at")
    if isinstance(raw_created, datetime):
        created = (
            raw_created
            if raw_created.tzinfo
            else raw_created.replace(tzinfo=timezone.utc)
        )
    elif isinstance(raw_created, str):
        try:
            created = datetime.fromisoformat(
                raw_created.replace("Z", "+00:00")
            )
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except ValueError:
            created = None
    if created is not None:
        end = created if end is None else max(end, created)
    if end is None:
        raise LogHistoryError(
            "Anchor log row has no parseable visit_time, access_time, or "
            "created_at; cannot determine the history search window.",
            status_code=422,
        )
    return end


def _history_window_from_anchor(
    anchor: dict[str, Any],
) -> tuple[datetime, datetime]:
    """
    ``(from_date, to_date)`` for fixed-calendar searches (e.g. backfill scripts).

    Live spatial analysis uses per-scope searches capped by
    ``SPATIAL_SCOPE_HISTORY_LIMIT`` without this ``from_date``.
    """
    end = _history_search_end_from_anchor(anchor)
    start = end - timedelta(days=HISTORY_WINDOW_DAYS)
    return start, end


def _merge_anchor_and_sort(
    records: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ensure focal row is present, dedupe by ``id``, sort by event time."""
    by_id: dict[str, dict[str, Any]] = {}
    for r in records:
        rid = r.get("id")
        if rid is not None:
            by_id[str(rid)] = r
    aid = anchor.get("id")
    if aid is not None:
        by_id[str(aid)] = anchor
    merged = list(by_id.values())
    return sorted(merged, key=_event_time_for_sort)


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform GET JSON against db-service; map transport/HTTP errors."""
    try:
        response = await client.get(url, params=params)
    except httpx.RequestError as exc:
        raise LogHistoryError(
            f"db-service request failed: {exc}",
            status_code=502,
        ) from exc
    if response.status_code == 404:
        raise LogHistoryError(
            "Requested log resource was not found.",
            status_code=404,
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise LogHistoryError(
            f"db-service returned an error: {exc}",
            status_code=502,
        ) from exc
    return response.json()


def _scope_history_limit(cfg: Settings | None = None) -> int:
    lim = int((cfg or settings).SPATIAL_SCOPE_HISTORY_LIMIT)
    return max(1, lim)


async def _fetch_scope_records(
    client: httpx.AsyncClient,
    url: str,
    *,
    filters: dict[str, Any],
    to_dt: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    """
    One search page for a scope: newest rows up to ``to_dt``, capped at ``limit``.

    Omits ``from_date`` so thin scopes (e.g. security) can reach further back
    when needed instead of sharing one short calendar window with estate-wide.
    """
    params: dict[str, Any] = {
        "to_date": _format_query_datetime(to_dt),
        "limit": limit,
        "page": 1,
    }
    for key, value in filters.items():
        if value is not None:
            params[key] = value
    data = await _get_json(client, url, params=params)
    items = data.get("items") or []
    return items if isinstance(items, list) else []


async def _wrangled_scope_rows(
    records: list[dict[str, Any]],
    anchor: dict[str, Any],
) -> list[dict[str, Any]]:
    """Merge anchor, dedupe, sort, and wrangle rows for one scope cohort."""
    from app.pipeline.data_wrangler import wrangle_visit_records

    merged = _merge_anchor_and_sort(records, anchor)
    if not merged:
        return []
    return await wrangle_visit_records(merged)


async def _wrangled_focal_only(anchor: dict[str, Any]) -> list[dict[str, Any]]:
    """Wrangle the anchor row alone (temporal scope — no history fetch)."""
    return await _wrangled_scope_rows([], anchor)


async def _load_visitor_log_slices(
    client: httpx.AsyncClient,
    cfg: Settings,
    *,
    anchor: dict[str, Any],
    payload: CodeValidationPayload,
    search_url: str,
) -> LogHistorySlices:
    """
    Parallel scope searches for a visitor-log anchor.

    * temporal — focal anchor only (no search; clock features)
    * resident — ``estate_id`` + ``user_id``
    * estate-wide — ``estate_id`` only (all estate traffic; noisy)
    * visitor — ``user_id`` + anchor ``visitor_fullname``
    * security — ``estate_id`` + ``security_id``
    """
    to_dt = _history_search_end_from_anchor(anchor)
    limit = _scope_history_limit(cfg)
    eid = str(payload.estate_id)
    uid = str(payload.user_id)
    sec = str(payload.security_id)

    resident_filters = {"estate_id": eid, "user_id": uid}
    estate_filters = {"estate_id": eid}
    security_filters = {"estate_id": eid, "security_id": sec}
    visitor_filters: dict[str, Any] = {"user_id": uid}
    vname = anchor.get("visitor_fullname")
    if isinstance(vname, str) and vname.strip():
        visitor_filters["visitor_fullname"] = vname.strip()

    temporal_task = _wrangled_focal_only(anchor)
    estate_raw, visitor_raw, resident_raw, security_raw = await asyncio.gather(
        _fetch_scope_records(
            client,
            search_url,
            filters=estate_filters,
            to_dt=to_dt,
            limit=limit,
        ),
        _fetch_scope_records(
            client,
            search_url,
            filters=visitor_filters,
            to_dt=to_dt,
            limit=limit,
        ),
        _fetch_scope_records(
            client,
            search_url,
            filters=resident_filters,
            to_dt=to_dt,
            limit=limit,
        ),
        _fetch_scope_records(
            client,
            search_url,
            filters=security_filters,
            to_dt=to_dt,
            limit=limit,
        ),
    )

    (
        temporal_clean,
        estate_clean,
        visitor_clean,
        resident_clean,
        security_clean,
    ) = await asyncio.gather(
        temporal_task,
        _wrangled_scope_rows(estate_raw, anchor),
        _wrangled_scope_rows(visitor_raw, anchor),
        _wrangled_scope_rows(resident_raw, anchor),
        _wrangled_scope_rows(security_raw, anchor),
    )

    if not (
        temporal_clean
        or estate_clean
        or visitor_clean
        or resident_clean
        or security_clean
    ):
        raise LogHistoryError(
            "No log rows available for analysis after per-scope fetch; "
            "anchor could not be merged into any scope cohort.",
            status_code=422,
        )

    trace(
        "log-fetch",
        "visitor log per-scope history fetched and wrangled",
        scope_limit=limit,
        search_end=_format_query_datetime(to_dt),
        anchor_id=anchor.get("id"),
        temporal_rows=len(temporal_clean),
        estate_wide_rows=len(estate_clean),
        visitor_specific_rows=len(visitor_clean),
        resident_specific_rows=len(resident_clean),
        security_specific_rows=len(security_clean),
    )

    return LogHistorySlices(
        source="visitor_log",
        payload=payload,
        focal_record=anchor,
        merged_full=estate_clean,
        temporal=temporal_clean,
        estate_wide=estate_clean,
        visitor_specific=visitor_clean,
        resident_specific=resident_clean,
        security_specific=security_clean,
    )


async def _load_resident_log_slices(
    client: httpx.AsyncClient,
    cfg: Settings,
    *,
    anchor: dict[str, Any],
    payload: CodeValidationPayload,
    search_url: str,
) -> LogHistorySlices:
    """
    Parallel scope searches for a resident-log anchor.

    * temporal — focal anchor only (no search)
    * resident — ``estate_id`` + ``user_id``
    * estate-wide — ``estate_id`` only
    * security — ``estate_id`` + ``security_id``

    Visitor-scope history is not fetched (resident anomaly scans omit it).
    """
    to_dt = _history_search_end_from_anchor(anchor)
    limit = _scope_history_limit(cfg)
    eid = str(payload.estate_id)
    uid = str(payload.user_id)
    sec = str(payload.security_id)

    resident_filters = {"estate_id": eid, "user_id": uid}
    estate_filters = {"estate_id": eid}
    security_filters = {"estate_id": eid, "security_id": sec}

    temporal_task = _wrangled_focal_only(anchor)
    estate_raw, resident_raw, security_raw = await asyncio.gather(
        _fetch_scope_records(
            client,
            search_url,
            filters=estate_filters,
            to_dt=to_dt,
            limit=limit,
        ),
        _fetch_scope_records(
            client,
            search_url,
            filters=resident_filters,
            to_dt=to_dt,
            limit=limit,
        ),
        _fetch_scope_records(
            client,
            search_url,
            filters=security_filters,
            to_dt=to_dt,
            limit=limit,
        ),
    )

    (
        temporal_clean,
        estate_clean,
        resident_clean,
        security_clean,
    ) = await asyncio.gather(
        temporal_task,
        _wrangled_scope_rows(estate_raw, anchor),
        _wrangled_scope_rows(resident_raw, anchor),
        _wrangled_scope_rows(security_raw, anchor),
    )

    if not (
        temporal_clean or estate_clean or resident_clean or security_clean
    ):
        raise LogHistoryError(
            "No log rows available for analysis after per-scope fetch; "
            "anchor could not be merged into any scope cohort.",
            status_code=422,
        )

    trace(
        "log-fetch",
        "resident log per-scope history fetched and wrangled",
        scope_limit=limit,
        search_end=_format_query_datetime(to_dt),
        anchor_id=anchor.get("id"),
        temporal_rows=len(temporal_clean),
        estate_wide_rows=len(estate_clean),
        visitor_specific_rows=0,
        resident_specific_rows=len(resident_clean),
        security_specific_rows=len(security_clean),
    )

    return LogHistorySlices(
        source="resident_log",
        payload=payload,
        focal_record=anchor,
        merged_full=estate_clean,
        temporal=temporal_clean,
        estate_wide=estate_clean,
        visitor_specific=[],
        resident_specific=resident_clean,
        security_specific=security_clean,
    )


async def load_log_records_for_analysis(
    client: httpx.AsyncClient,
    settings: Settings,
    payload: CodeValidationPayload,
) -> LogHistorySlices:
    """
    Load the anchor and fetch **separate** capped history cohorts per scope.

    Each scope uses db-service search with scope-specific filters and
    ``limit=SPATIAL_SCOPE_HISTORY_LIMIT`` (default 40), ending at the anchor
    time. No shared ``from_date`` window — security and visitor cohorts can
    reach further back independently.

    * **Temporal** — focal row only (no db search; features are anchor clock
      fields). Detector history uses stored temporal vectors from the resident
      cohort at scoring time.
    * **Resident** — ``estate_id`` + ``user_id`` (both anchor types).
    * **Estate-wide** — ``estate_id`` only (both anchor types; down-weighted
      in ensemble config because it is noisier).
    * **Visitor-specific** — ``user_id`` + ``visitor_fullname`` (visitor
      anchors only; not fetched for resident anchors).
    * **Security-specific** — ``estate_id`` + ``security_id`` (both anchor
      types).

    Scope fetches and wrangling run concurrently via ``asyncio.gather``.

    Raises:
        LogHistoryError: If the anchor cannot be loaded or no scope cohort
        contains the anchor after merge.
    """
    if payload.visitor_log_id is not None:
        anchor_url = _db_url(
            settings,
            f"api/v1/codeservice/visitorlog/{payload.visitor_log_id}",
        )
        anchor = await _get_json(client, anchor_url)
        search_url = _db_url(settings, "api/v1/codeservice/visitorlog/search")
        return await _load_visitor_log_slices(
            client,
            settings,
            anchor=anchor,
            payload=payload,
            search_url=search_url,
        )

    if payload.resident_log_id is not None:
        anchor_url = _db_url(
            settings,
            f"api/v1/codeservice/residentlog/{payload.resident_log_id}",
        )
        anchor = await _get_json(client, anchor_url)
        search_url = _db_url(settings, "api/v1/codeservice/residentlog/search")
        return await _load_resident_log_slices(
            client,
            settings,
            anchor=anchor,
            payload=payload,
            search_url=search_url,
        )

    raise LogHistoryError(
        "Exactly one of visitor_log_id or resident_log_id is required.",
        status_code=422,
    )


def history_window_days() -> int:
    """Return the fixed look-back length (days) used for log search windows."""
    return HISTORY_WINDOW_DAYS
