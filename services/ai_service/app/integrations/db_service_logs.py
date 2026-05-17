"""Pull visitor/resident log rows from db-service (codeservice paths)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.core.exceptions import LogHistoryError
from app.domain.scopes import AnalysisScope
from app.models.anomaly_schema import CodeValidationPayload

logger = logging.getLogger(__name__)

_LOG_PAGE_SIZE = 100
HISTORY_WINDOW_DAYS = 30


@dataclass(frozen=True)
class LogHistorySlices:
    """
    Wrangled log rows for one anchor-centred window, split for feature scopes.

    All list fields are **already passed through** ``wrangle_visit_records``
    (null/empty stripped). ``focal_record`` remains the raw anchor dict from
    db-service for timestamps and ids used in focal features.
    """

    source: Literal["visitor_log", "resident_log"]
    payload: CodeValidationPayload
    focal_record: dict[str, Any]
    merged_full: list[dict[str, Any]]
    estate_wide: list[dict[str, Any]]
    visitor_specific: list[dict[str, Any]]
    resident_specific: list[dict[str, Any]]
    security_specific: list[dict[str, Any]]

    def rows_for_analysis_scope(
        self, scope: AnalysisScope
    ) -> list[dict[str, Any]]:
        """Wrangled rows to pass into feature engineering for ``scope``."""
        mapping: dict[AnalysisScope, list[dict[str, Any]]] = {
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


def _history_window_from_anchor(
    anchor: dict[str, Any],
) -> tuple[datetime, datetime]:
    """
    ``(from_date, to_date)`` for search: one month **back from** the anchor row's
    recorded event time (not from wall-clock now).
    """
    end = _record_event_time_or_none(anchor)
    if end is None:
        raise LogHistoryError(
            "Anchor log row has no parseable visit_time, access_time, or "
            "created_at; cannot determine the history search window.",
            status_code=422,
        )
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


def _norm_name(value: Any) -> str:
    """Lowercase stripped string for visitor-name comparisons; non-strings yield empty."""
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _split_visitor_log_cleaned(
    cleaned_merged: list[dict[str, Any]],
    anchor: dict[str, Any],
    payload: CodeValidationPayload,
) -> LogHistorySlices:
    """Partition wrangled visitor-log rows by analysis scope."""
    estate = list(cleaned_merged)
    uid = str(payload.user_id)
    sec = str(payload.security_id)
    aname = _norm_name(anchor.get("visitor_fullname"))
    visitor_specific = [
        r
        for r in cleaned_merged
        if aname and _norm_name(r.get("visitor_fullname")) == aname
    ]
    resident_specific = [
        r for r in cleaned_merged if str(r.get("user_id")) == uid
    ]
    security_specific = [
        r for r in cleaned_merged if str(r.get("security_id")) == sec
    ]
    return LogHistorySlices(
        source="visitor_log",
        payload=payload,
        focal_record=anchor,
        merged_full=estate,
        estate_wide=estate,
        visitor_specific=visitor_specific,
        resident_specific=resident_specific,
        security_specific=security_specific,
    )


def _split_resident_log_cleaned(
    cleaned_merged: list[dict[str, Any]],
    anchor: dict[str, Any],
    payload: CodeValidationPayload,
) -> LogHistorySlices:
    """
    Partition wrangled resident-log rows by analysis scope.

    Visitor-scope uses ``hashed_code`` alignment with the anchor (resident rows
    have no visitor name).
    """
    estate = list(cleaned_merged)
    uid = str(payload.user_id)
    sec = str(payload.security_id)
    h_anchor = anchor.get("hashed_code")
    visitor_specific = [
        r
        for r in cleaned_merged
        if h_anchor is not None and r.get("hashed_code") == h_anchor
    ]
    resident_specific = [
        r for r in cleaned_merged if str(r.get("user_id")) == uid
    ]
    security_specific = [
        r for r in cleaned_merged if str(r.get("security_id")) == sec
    ]
    return LogHistorySlices(
        source="resident_log",
        payload=payload,
        focal_record=anchor,
        merged_full=estate,
        estate_wide=estate,
        visitor_specific=visitor_specific,
        resident_specific=resident_specific,
        security_specific=security_specific,
    )


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


async def _fetch_all_search_pages(
    client: httpx.AsyncClient,
    url: str,
    base_params: dict[str, Any],
    *,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict[str, Any]]:
    """Page through search results until all rows in the date window are read."""
    params: dict[str, Any] = {
        "from_date": _format_query_datetime(from_dt),
        "to_date": _format_query_datetime(to_dt),
        "limit": _LOG_PAGE_SIZE,
        **base_params,
    }
    all_items: list[dict[str, Any]] = []
    page = 1
    while True:
        page_params = {**params, "page": page}
        data = await _get_json(client, url, params=page_params)
        items = data.get("items") or []
        total = int(data.get("total") or 0)
        all_items.extend(items)
        if not items or len(all_items) >= total or len(items) < _LOG_PAGE_SIZE:
            break
        page += 1
    return all_items


async def load_log_records_for_analysis(
    client: httpx.AsyncClient,
    settings: Settings,
    payload: CodeValidationPayload,
) -> LogHistorySlices:
    """
    Load the anchor, fetch the wide time window from db-service, merge and sort,
    **wrangle** the merged rows, then **split** the wrangled rows for scopes:

    * **Estate-wide** — full wrangled window (visitor: host ``user_id`` visits;
      resident: estate-wide accesses).
    * **Visitor-specific** — visitor logs: same ``visitor_fullname`` as anchor;
      resident logs: same ``hashed_code`` as anchor.
    * **Resident-specific** — ``payload.user_id``.
    * **Security-specific** — ``payload.security_id``.

    Returns only wrangled row lists plus the raw ``focal_record`` (anchor).

    Raises:
        LogHistoryError: If the anchor cannot be loaded, the window is empty, or
        HTTP transport fails when calling db-service.
    """
    # Local import avoids ``app.pipeline`` package init (orchestrator) while this
    # module is still loading.
    from app.pipeline.data_wrangler import wrangle_visit_records

    if payload.visitor_log_id is not None:
        anchor_url = _db_url(
            settings,
            f"api/v1/codeservice/visitorlog/{payload.visitor_log_id}",
        )
        anchor = await _get_json(client, anchor_url)
        from_dt, to_dt = _history_window_from_anchor(anchor)
        search_url = _db_url(settings, "api/v1/codeservice/visitorlog/search")
        records = await _fetch_all_search_pages(
            client,
            search_url,
            {"user_id": str(payload.user_id)},
            from_dt=from_dt,
            to_dt=to_dt,
        )
        logger.debug(
            "visitor log wide history rows=%s window=%s..%s",
            len(records),
            _format_query_datetime(from_dt),
            _format_query_datetime(to_dt),
        )
        if not records:
            raise LogHistoryError(
                "No log rows returned for the one-month window ending at the "
                "anchor visit/access time; analysis cannot proceed.",
                status_code=422,
            )
        merged_raw = _merge_anchor_and_sort(records, anchor)
        cleaned_merged = await wrangle_visit_records(merged_raw)
        return _split_visitor_log_cleaned(cleaned_merged, anchor, payload)

    if payload.resident_log_id is not None:
        anchor_url = _db_url(
            settings,
            f"api/v1/codeservice/residentlog/{payload.resident_log_id}",
        )
        anchor = await _get_json(client, anchor_url)
        from_dt, to_dt = _history_window_from_anchor(anchor)
        search_url = _db_url(settings, "api/v1/codeservice/residentlog/search")
        records = await _fetch_all_search_pages(
            client,
            search_url,
            {"estate_id": str(payload.estate_id)},
            from_dt=from_dt,
            to_dt=to_dt,
        )
        logger.debug(
            "resident log wide history rows=%s window=%s..%s",
            len(records),
            _format_query_datetime(from_dt),
            _format_query_datetime(to_dt),
        )
        if not records:
            raise LogHistoryError(
                "No log rows returned for the one-month window ending at the "
                "anchor visit/access time; analysis cannot proceed.",
                status_code=422,
            )
        merged_raw = _merge_anchor_and_sort(records, anchor)
        cleaned_merged = await wrangle_visit_records(merged_raw)
        return _split_resident_log_cleaned(cleaned_merged, anchor, payload)

    raise LogHistoryError(
        "Exactly one of visitor_log_id or resident_log_id is required.",
        status_code=422,
    )


def history_window_days() -> int:
    """Return the fixed look-back length (days) used for log search windows."""
    return HISTORY_WINDOW_DAYS
