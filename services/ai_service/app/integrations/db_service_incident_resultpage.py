"""Fetch incident result-page overview and list payloads from db-service."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings
from app.integrations.db_service_prediction_result import _get_json, _params


async def fetch_incident_overview(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
    from_date: datetime | None,
    to_date: datetime | None,
) -> dict[str, Any]:
    """
    GET db-service incident result-page overview counts.

    Arguments:
        client: Shared HTTP client.
        settings: Service settings with the db-service base URL.
        estate_id: Estate to summarise.
        from_date: Inclusive ``created_at`` lower bound, or open.
        to_date: Inclusive ``created_at`` upper bound, or open.

    Returns:
        Estate identity and reporter-role counts.
    """
    return await _get_json(
        client,
        settings,
        "api/v1/ai-features/incident-report/result-page/overview",
        _params(estate_id=estate_id, from_date=from_date, to_date=to_date),
    )


async def fetch_incident_reports(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID,
    categories: list[str] | None,
    user_types: list[str] | None,
    from_date: datetime | None,
    to_date: datetime | None,
    page: int,
    limit: int,
) -> dict[str, Any]:
    """
    GET db-service incident result-page search.

    Arguments:
        client: Shared HTTP client.
        settings: Service settings with the db-service base URL.
        estate_id: Estate to list.
        categories: Fixed taxonomy values, or ``None`` for all.
        user_types: ``resident`` / ``security``, or ``None`` for all.
        from_date: Inclusive ``created_at`` lower bound, or open.
        to_date: Inclusive ``created_at`` upper bound, or open.
        page: 1-based page number.
        limit: Page size.

    Returns:
        Paginated incident rows plus ``reporter_user_type``.
    """
    return await _get_json(
        client,
        settings,
        "api/v1/ai-features/incident-report/result-page/search",
        _params(
            estate_id=estate_id,
            categories=categories,
            user_types=user_types,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
        ),
    )
