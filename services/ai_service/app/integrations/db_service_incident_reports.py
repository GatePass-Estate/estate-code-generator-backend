"""
Paginated incident search against db-service for ai-service analyse.

Reads ``core.incidentreport`` (migration ``c17962ae653d``). Search date filters
apply to ``created_at``. Rows include optional ``title``, ``custom_category``,
and ``category`` as a PostgreSQL enum array.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import IncidentReportError

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


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
    except httpx.RequestError as exc:
        raise IncidentReportError(
            f"db-service request failed: {exc}",
            status_code=502,
        ) from exc
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise IncidentReportError(
            f"db-service returned an error: {exc}",
            status_code=502,
        ) from exc
    return response.json()


async def load_incident_reports_for_estate(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
    from_date: datetime | None,
    to_date: datetime | None,
    max_records: int,
) -> list[dict[str, Any]]:
    """
    Page ``GET /api/v1/codeservice/incidentreport/search`` for one estate.

    Results are ordered by ``created_at`` descending in db-service. Stops when
    ``max_records`` is reached or the server reports no further pages.

    Raises:
        IncidentReportError: On transport or HTTP errors from db-service.
    """
    url = _db_url(settings, "api/v1/codeservice/incidentreport/search")
    collected: list[dict[str, Any]] = []
    page = 1
    while len(collected) < max_records:
        limit = min(_PAGE_SIZE, max_records - len(collected))
        params: dict[str, Any] = {
            "estate_id": str(estate_id),
            "page": page,
            "limit": limit,
        }
        if from_date is not None:
            params["from_date"] = _format_query_datetime(from_date)
        if to_date is not None:
            params["to_date"] = _format_query_datetime(to_date)
        data = await _get_json(client, url, params=params)
        items = data.get("items") or []
        collected.extend(items)
        total = int(data.get("total") or 0)
        if not items or len(collected) >= total:
            break
        page += 1

    logger.debug(
        "incident reports fetched estate_id=%s rows=%s",
        estate_id,
        len(collected),
    )
    return collected[:max_records]
