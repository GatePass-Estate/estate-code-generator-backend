"""
Estate payment lookup for incident summarise tier gating (free vs paid).

Used by ``IncidentReportOrchestrator`` to decide whether to run EDA + LLM.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import IncidentReportError
from app.integrations.db_service_logs import _db_url

logger = logging.getLogger(__name__)

# Until ``core.estates`` exposes a payment flag, treat lookups as active.
_DEFAULT_PAYMENT_ACTIVE = True


async def fetch_estate_payment_active(
    client: httpx.AsyncClient,
    settings: Settings,
    estate_id: UUID,
) -> bool:
    """
    Return whether the paid incident summary tier should run.

    Reads ``payment_status`` or ``is_paid`` from user-profile estate GET when
    present; otherwise defaults to ``True`` (``_DEFAULT_PAYMENT_ACTIVE``).
    """
    url = _db_url(settings, f"api/v1/userprofile/estates/{estate_id}")
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.RequestError as exc:
        logger.warning(
            "estate payment lookup failed estate_id=%s: %s; default=%s",
            estate_id,
            exc,
            _DEFAULT_PAYMENT_ACTIVE,
        )
        return _DEFAULT_PAYMENT_ACTIVE
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise IncidentReportError(
                f"Estate {estate_id} not found.",
                status_code=404,
            ) from exc
        logger.warning(
            "estate payment lookup HTTP error estate_id=%s: %s; default=%s",
            estate_id,
            exc,
            _DEFAULT_PAYMENT_ACTIVE,
        )
        return _DEFAULT_PAYMENT_ACTIVE

    data = response.json()
    if not isinstance(data, dict):
        return _DEFAULT_PAYMENT_ACTIVE

    if "payment_status" in data:
        raw = data["payment_status"]
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("paid", "active", "true", "1")
        return bool(raw)

    if "is_paid" in data:
        return bool(data["is_paid"])

    return _DEFAULT_PAYMENT_ACTIVE
