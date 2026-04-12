"""Pull visitor/resident log rows from db-service (codeservice paths)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import httpx

from app.core.config import Settings
from app.core.exceptions import LogHistoryError
from app.models.schemas import CodeValidationPayload

logger = logging.getLogger(__name__)

_LOG_PAGE_SIZE = 100
_HISTORY_DAYS = 30


def _db_url(settings: Settings, path: str) -> str:
    base = settings.DB_SERVICE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def _month_window_utc() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=_HISTORY_DAYS)
    return start, now


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
) -> list[dict[str, Any]]:
    from_dt, to_dt = _month_window_utc()
    params = {
        **base_params,
        "from_date": from_dt.isoformat(),
        "to_date": to_dt.isoformat(),
        "limit": _LOG_PAGE_SIZE,
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
) -> list[dict[str, Any]]:
    """
    Resolve anchor log id, then load up to one month of matching log rows.

    Filters visitor/resident search by ``security_id`` from the payload.
    Fail-closed: missing anchor or zero rows after search.
    """
    from_dt, to_dt = _month_window_utc()
    sec = str(payload.security_id)

    if payload.visitor_log_id is not None:
        anchor_url = _db_url(
            settings,
            f"api/v1/codeservice/visitorlog/{payload.visitor_log_id}",
        )
        await _get_json(client, anchor_url)
        search_url = _db_url(settings, "api/v1/codeservice/visitorlog/search")
        records = await _fetch_all_search_pages(
            client,
            search_url,
            {
                "security_id": sec,
                "hashed_code": payload.hashed_code,
            },
        )
        logger.debug(
            "visitor log history rows=%s window=%s..%s",
            len(records),
            from_dt.isoformat(),
            to_dt.isoformat(),
        )
    elif payload.resident_log_id is not None:
        anchor_url = _db_url(
            settings,
            f"api/v1/codeservice/residentlog/{payload.resident_log_id}",
        )
        await _get_json(client, anchor_url)
        search_url = _db_url(settings, "api/v1/codeservice/residentlog/search")
        records = await _fetch_all_search_pages(
            client,
            search_url,
            {
                "user_id": str(payload.user_id),
                "estate_id": str(payload.estate_id),
                "security_id": sec,
                "hashed_code": payload.hashed_code,
            },
        )
        logger.debug(
            "resident log history rows=%s window=%s..%s",
            len(records),
            from_dt.isoformat(),
            to_dt.isoformat(),
        )
    else:
        raise LogHistoryError(
            "Exactly one of visitor_log_id or resident_log_id is required.",
            status_code=422,
        )

    if not records:
        raise LogHistoryError(
            "No log rows returned for the configured one-month window; "
            "analysis cannot proceed.",
            status_code=422,
        )
    return records
