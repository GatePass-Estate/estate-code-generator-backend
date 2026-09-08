"""Read and write ``core.ai_response`` rows via db-service."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import ResultPageError
from app.integrations.db_service_logs import _db_url
from app.integrations.db_service_prediction_result import _qs_dt

logger = logging.getLogger(__name__)


async def fetch_ai_summary(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    feature_key: str,
    lookup_key: str,
) -> dict[str, Any] | None:
    """
    GET db-service ``/ai-features/ai-response``.

    Returns the JSON object, or ``None`` when no cache row exists (404).
    """
    url = _db_url(settings, "api/v1/ai-features/ai-response")
    try:
        response = await client.get(
            url,
            params={"feature_key": feature_key, "lookup_key": lookup_key},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise ResultPageError(
            f"db-service AI summary lookup failed: {exc}",
            status_code=502,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ResultPageError(
            f"db-service AI summary lookup HTTP error: {exc}",
            status_code=502,
        ) from exc
    data = response.json()
    if not isinstance(data, dict):
        raise ResultPageError(
            "db-service returned a non-object payload.",
            status_code=502,
        )
    return data


async def upsert_ai_summary(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    feature_key: str,
    lookup_key: str,
    prediction_result_id: UUID | None = None,
    estate_id: UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    tier1: dict[str, Any] | None = None,
    tier2: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """PUT db-service ``/ai-features/ai-response`` and return the stored row."""
    url = _db_url(settings, "api/v1/ai-features/ai-response")
    body: dict[str, Any] = {
        "feature_key": feature_key,
        "lookup_key": lookup_key,
    }
    if prediction_result_id is not None:
        body["prediction_result_id"] = str(prediction_result_id)
    if estate_id is not None:
        body["estate_id"] = str(estate_id)
    if from_date is not None:
        body["from_date"] = _qs_dt(from_date)
    if to_date is not None:
        body["to_date"] = _qs_dt(to_date)
    if tier1 is not None:
        body["tier1"] = tier1
    if tier2 is not None:
        body["tier2"] = tier2
    try:
        response = await client.put(url, json=body)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise ResultPageError(
            f"db-service AI summary cache failed: {exc}",
            status_code=502,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ResultPageError(
            f"db-service AI summary cache HTTP error: {exc}",
            status_code=502,
        ) from exc
    data = response.json()
    if not isinstance(data, dict):
        raise ResultPageError(
            "db-service returned a non-object payload.",
            status_code=502,
        )
    return data
