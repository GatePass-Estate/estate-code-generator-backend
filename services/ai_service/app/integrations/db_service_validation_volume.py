"""
Pull estate validation events from db-service for volume and temporal analysis.

Pages ``GET api/v1/codeservice/visitorlog/search`` and
``.../residentlog/search`` filtered by ``estate_id`` (and optionally a date
window), and returns parsed event timestamps used to build a daily count series.

Shared by ``VolumeForecastOrchestrator`` (bounded window + ``max_records``) and
``TemporalAnomalyOrchestrator`` (full history, no date filter or record cap).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import VolumeForecastError
from app.domain.forecast_target import ForecastTarget

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100


@dataclass(frozen=True)
class ValidationEventsResult:
    """Parsed validation event times plus which log tables were queried."""

    timestamps: list[datetime]
    includes: tuple[str, ...]


def _db_url(settings: Settings, path: str) -> str:
    base = settings.DB_SERVICE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _format_query_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _includes_for_target(target: ForecastTarget) -> tuple[str, ...]:
    includes: list[str] = []
    if target in (ForecastTarget.VISITOR, ForecastTarget.COMBINED):
        includes.append("visitor_log")
    if target in (ForecastTarget.RESIDENT, ForecastTarget.COMBINED):
        includes.append("resident_log")
    return tuple(includes)


def _record_event_time_or_none(rec: dict[str, Any]) -> datetime | None:
    """Parse primary event time (visit/access/created) or return None."""
    for key in ("visit_time", "access_time", "created_at"):
        raw = rec.get(key)
        if raw is None:
            continue
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        if isinstance(raw, str):
            v = raw.replace("Z", "+00:00")
            try:
                ts = datetime.fromisoformat(v)
            except ValueError:
                continue
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return None


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
    except httpx.RequestError as exc:
        raise VolumeForecastError(
            f"db-service request failed: {exc}",
            status_code=502,
        ) from exc
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise VolumeForecastError(
            f"db-service returned an error: {exc}",
            status_code=502,
        ) from exc
    return response.json()


async def _load_search_timestamps(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    search_path: str,
    estate_id: UUID | str,
    from_dt: datetime | None,
    to_dt: datetime | None,
    max_records: int | None,
) -> list[datetime]:
    """Page one search endpoint and collect parsed event timestamps."""
    url = _db_url(settings, search_path)
    timestamps: list[datetime] = []
    page = 1
    fetched = 0
    total = 0
    while True:
        if max_records is not None and len(timestamps) >= max_records:
            break
        limit = (
            _PAGE_SIZE
            if max_records is None
            else min(_PAGE_SIZE, max_records - len(timestamps))
        )
        params: dict[str, Any] = {
            "estate_id": str(estate_id),
            "page": page,
            "limit": limit,
        }
        if from_dt is not None:
            params["from_date"] = _format_query_datetime(from_dt)
        if to_dt is not None:
            params["to_date"] = _format_query_datetime(to_dt)
        data = await _get_json(client, url, params=params)
        items = data.get("items") or []
        total = int(data.get("total") or 0)
        fetched += len(items)
        for row in items:
            ts = _record_event_time_or_none(row)
            if ts is not None:
                timestamps.append(ts)
                if max_records is not None and len(timestamps) >= max_records:
                    break
        if not items or fetched >= total or len(items) < limit:
            break
        page += 1
    if max_records is not None:
        return timestamps[:max_records]
    return timestamps


async def load_validation_events(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID | str,
    target: ForecastTarget,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    max_records: int | None = None,
    raise_if_empty: bool = False,
    empty_message: str = "No validation events found for the estate.",
    empty_status_code: int = 404,
) -> ValidationEventsResult:
    """
    Return event timestamps for the estate.

    When ``from_dt`` / ``to_dt`` are omitted, the full history is paged with no
    date filter. When ``max_records`` is omitted, all matching rows are read.

    ``VISITOR`` reads visitor logs, ``RESIDENT`` reads resident logs, and
    ``COMBINED`` merges both. Rows without a parseable timestamp are skipped.

    Raises:
        VolumeForecastError: On transport or HTTP errors from db-service, or
            when ``raise_if_empty`` is set and no parseable timestamps remain.
    """
    timestamps: list[datetime] = []
    if target in (ForecastTarget.VISITOR, ForecastTarget.COMBINED):
        timestamps.extend(
            await _load_search_timestamps(
                client,
                settings,
                search_path="api/v1/codeservice/visitorlog/search",
                estate_id=estate_id,
                from_dt=from_dt,
                to_dt=to_dt,
                max_records=max_records,
            )
        )
    if target in (ForecastTarget.RESIDENT, ForecastTarget.COMBINED):
        timestamps.extend(
            await _load_search_timestamps(
                client,
                settings,
                search_path="api/v1/codeservice/residentlog/search",
                estate_id=estate_id,
                from_dt=from_dt,
                to_dt=to_dt,
                max_records=max_records,
            )
        )

    window_start = (
        _format_query_datetime(from_dt) if from_dt is not None else "full"
    )
    window_end = _format_query_datetime(to_dt) if to_dt is not None else "full"
    logger.debug(
        "validation events estate_id=%s target=%s rows=%s window=%s..%s",
        estate_id,
        target.value,
        len(timestamps),
        window_start,
        window_end,
    )

    if raise_if_empty and not timestamps:
        raise VolumeForecastError(
            empty_message,
            status_code=empty_status_code,
        )

    return ValidationEventsResult(
        timestamps=timestamps,
        includes=_includes_for_target(target),
    )
