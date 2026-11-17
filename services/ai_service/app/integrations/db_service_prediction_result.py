"""Fetch prediction-result overview and list payloads from db-service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import ResultPageError
from app.integrations.db_service_logs import _db_url

logger = logging.getLogger(__name__)


def _qs_dt(dt: datetime | None) -> str | None:
    """Format a datetime as UTC ISO-8601 with a trailing Z, or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _params(**kwargs: Any) -> dict[str, Any]:
    """Drop Nones and empty lists; stringify datetimes and UUIDs."""
    out: dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            out[key] = list(value)
        elif isinstance(value, datetime):
            out[key] = _qs_dt(value)
        elif isinstance(value, UUID):
            out[key] = str(value)
        else:
            out[key] = value
    return out


async def _get_json(
    client: httpx.AsyncClient,
    settings: Settings,
    path: str,
    params: dict[str, Any],
    *,
    not_found_detail: str = "Estate not found.",
) -> dict[str, Any]:
    """GET ``path`` on db-service and return the JSON object body."""
    url = _db_url(settings, path)
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise ResultPageError(
            f"db-service prediction lookup failed: {exc}",
            status_code=502,
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            raise ResultPageError(not_found_detail, status_code=404) from exc
        raise ResultPageError(
            f"db-service prediction lookup HTTP error: {exc}",
            status_code=502,
        ) from exc
    data = response.json()
    if not isinstance(data, dict):
        raise ResultPageError(
            "db-service returned a non-object payload.",
            status_code=502,
        )
    return data


async def fetch_overview(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
    from_date: datetime | None,
    to_date: datetime | None,
) -> dict[str, Any]:
    """
    GET db-service ``/predictionresult/overview``.

    Returns estate identity, demographic counts, anomalous-instance
    counts, ``normal_sample``, and period-max maps.
    """
    return await _get_json(
        client,
        settings,
        "api/v1/codeservice/predictionresult/overview",
        _params(estate_id=estate_id, from_date=from_date, to_date=to_date),
    )


async def fetch_predictions(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
    severity: list[str] | None,
    gender: list[str] | None,
    user_type: list[str] | None,
    sort_order: str,
    from_date: datetime | None,
    to_date: datetime | None,
    page: int,
    limit: int,
) -> dict[str, Any]:
    """
    GET db-service ``/predictionresult/search``.

    Repeatable ``severity``, ``gender``, and ``user_type`` lists are
    forwarded as repeated query params.
    """
    return await _get_json(
        client,
        settings,
        "api/v1/codeservice/predictionresult/search",
        _params(
            estate_id=estate_id,
            severity=severity,
            gender=gender,
            user_type=user_type,
            sort_order=sort_order,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        ),
    )


async def fetch_case_demographic(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    prediction_id: UUID,
    estate_id: UUID,
    display_name: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> dict[str, Any]:
    """GET db-service case demographic for one prediction."""
    return await _get_json(
        client,
        settings,
        f"api/v1/codeservice/predictionresult/{prediction_id}/demographic",
        _params(
            estate_id=estate_id,
            display_name=display_name,
            from_date=from_date,
            to_date=to_date,
        ),
        not_found_detail="Prediction not found.",
    )


async def fetch_case_history(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    prediction_id: UUID,
    estate_id: UUID,
    display_name: str | None,
    history_limit: int,
) -> dict[str, Any]:
    """GET db-service prediction history for the same named person."""
    return await _get_json(
        client,
        settings,
        f"api/v1/codeservice/predictionresult/{prediction_id}/history",
        _params(
            estate_id=estate_id,
            display_name=display_name,
            history_limit=history_limit,
        ),
        not_found_detail="Prediction not found.",
    )


async def fetch_case_detail(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    prediction_id: UUID,
    estate_id: UUID,
    from_date: datetime | None,
    to_date: datetime | None,
) -> dict[str, Any]:
    """GET selected payload, cached summary, sample, and period maxes."""
    return await _get_json(
        client,
        settings,
        f"api/v1/codeservice/predictionresult/{prediction_id}/case",
        _params(
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
        ),
        not_found_detail="Prediction not found.",
    )


async def patch_ai_summary(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    prediction_id: UUID,
    tier1: dict[str, Any] | None = None,
    tier2: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """PATCH cached ``tier1`` / ``tier2`` summaries onto the row."""
    url = _db_url(
        settings,
        f"api/v1/codeservice/predictionresult/{prediction_id}/ai-summary",
    )
    body: dict[str, Any] = {}
    if tier1 is not None:
        body["tier1"] = tier1
    if tier2 is not None:
        body["tier2"] = tier2
    try:
        response = await client.patch(url, json=body)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise ResultPageError(
            f"db-service summary cache failed: {exc}",
            status_code=502,
        ) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise ResultPageError(
                "Prediction not found.", status_code=404
            ) from exc
        raise ResultPageError(
            f"db-service summary cache HTTP error: {exc}",
            status_code=502,
        ) from exc
    data = response.json()
    if not isinstance(data, dict):
        raise ResultPageError(
            "db-service returned a non-object payload.",
            status_code=502,
        )
    return data
