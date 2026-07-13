"""
Pull estate validation events from db-service for ARIMA volume forecasting.

Pages ``GET api/v1/codeservice/visitorlog/search`` and
``.../residentlog/search`` filtered by ``estate_id`` and a date window, and
returns only the parsed event timestamps used to build a daily count series.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import VolumeForecastError
from app.domain.forecast_target import ForecastTarget

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100


def _db_url(settings: Settings, path: str) -> str:
    base = settings.DB_SERVICE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _format_query_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


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
    estate_id: UUID,
    from_dt: datetime,
    to_dt: datetime,
    max_records: int,
) -> list[datetime]:
    """Page one search endpoint and collect parsed event timestamps."""
    url = _db_url(settings, search_path)
    timestamps: list[datetime] = []
    page = 1
    while len(timestamps) < max_records:
        limit = min(_PAGE_SIZE, max_records - len(timestamps))
        params: dict[str, Any] = {
            "estate_id": str(estate_id),
            "from_date": _format_query_datetime(from_dt),
            "to_date": _format_query_datetime(to_dt),
            "page": page,
            "limit": limit,
        }
        data = await _get_json(client, url, params=params)
        items = data.get("items") or []
        for row in items:
            ts = _record_event_time_or_none(row)
            if ts is not None:
                timestamps.append(ts)
        total = int(data.get("total") or 0)
        if not items or len(items) < limit or len(timestamps) >= total:
            break
        page += 1
    return timestamps


async def load_validation_events(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
    target: ForecastTarget,
    from_dt: datetime,
    to_dt: datetime,
    max_records: int,
) -> list[datetime]:
    """
    Return event timestamps for the estate in ``[from_dt, to_dt]``.

    ``VISITOR`` reads visitor logs, ``RESIDENT`` reads resident logs, and
    ``COMBINED`` merges both. Rows without a parseable timestamp are skipped.

    Raises:
        VolumeForecastError: On transport or HTTP errors from db-service.
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
    logger.debug(
        "validation events estate_id=%s target=%s rows=%s window=%s..%s",
        estate_id,
        target.value,
        len(timestamps),
        _format_query_datetime(from_dt),
        _format_query_datetime(to_dt),
    )
    return timestamps
