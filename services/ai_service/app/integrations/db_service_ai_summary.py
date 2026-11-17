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


DAILY_SUMMARY_LIMIT_MESSAGE = (
    "The daily limit for report summary has been reached. "
    "The limit will reset after UTC midnight."
)


async def consume_third_party_incident_summary(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
) -> dict[str, Any]:
    """
    Reserve one new third-party incident summary for ``estate_id``.

    db-service creates the estate row on the first call, resets the
    counter when the stored UTC date is not today, and rejects the
    call once today's count is already 100.

    Arguments:
        client: Shared HTTP client for this request.
        settings: Service settings, including the db-service URL.
        estate_id: Estate spending a generation.

    Returns:
        The stored estate id, UTC date, and counter after this call.

    Raises:
        ResultPageError: 429 when the daily limit is already reached;
            502 when db-service cannot be reached.
    """
    url = _db_url(settings, "api/v1/ai-features/incident-summary-generation")
    try:
        response = await client.post(url, json={"estate_id": str(estate_id)})
    except httpx.RequestError as exc:
        raise ResultPageError(
            f"db-service summary generation cap failed: {exc}",
            status_code=502,
        ) from exc
    if response.status_code == 429:
        detail = DAILY_SUMMARY_LIMIT_MESSAGE
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("detail"), str):
            detail = body["detail"]
        raise ResultPageError(detail, status_code=429)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ResultPageError(
            f"db-service summary generation cap HTTP error: {exc}",
            status_code=502,
        ) from exc
    data = response.json()
    if not isinstance(data, dict):
        raise ResultPageError(
            "db-service returned a non-object payload.",
            status_code=502,
        )
    return data
