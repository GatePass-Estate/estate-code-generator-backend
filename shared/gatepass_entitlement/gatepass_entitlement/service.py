"""Revenue-service catalog entitlement checks."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException

from gatepass_entitlement.config import settings
from gatepass_entitlement.http import get_json, join_url

logger = logging.getLogger(__name__)

_CHECK_PATH = "api/v1/entitlements/check"


def _check_url(revenue_base_url: str) -> str:
    """Return the catalog entitlement check URL."""
    return join_url(revenue_base_url, _CHECK_PATH)


async def fetch_service_entitlement(
    revenue_base_url: str,
    *,
    estate_id: str,
    service_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """
    Fetch a catalog entitlement payload without requiring ``allowed``.

    Returns:
        Response dict, or None when revenue-service is unreachable.
    """
    params = {"estate_id": str(estate_id), "service_key": service_key}
    try:
        response = await get_json(
            _check_url(revenue_base_url),
            params,
            client=client,
        )
        response.raise_for_status()
    except Exception:
        logger.exception(
            "Entitlement lookup failed estate_id=%s service_key=%s",
            estate_id,
            service_key,
        )
        return None
    data = response.json() if response.content else None
    return data if isinstance(data, dict) else None


async def check_service_entitlement(
    revenue_base_url: str,
    *,
    estate_id: str,
    service_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Call revenue-service entitlement check for one service_key.

    Returns:
        Parsed JSON body from revenue-service.

    Raises:
        HTTPException: 403 when not allowed; 404 when unknown key;
            502 when revenue-service fails.
    """
    params = {"estate_id": str(estate_id), "service_key": service_key}
    try:
        response = await get_json(
            _check_url(revenue_base_url),
            params,
            client=client,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown service_key '{service_key}'.",
            ) from exc
        logger.exception(
            "Entitlement check HTTP error estate_id=%s service_key=%s "
            "status=%s",
            estate_id,
            service_key,
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to verify service entitlement.",
        ) from exc
    except httpx.RequestError as exc:
        logger.exception(
            "Entitlement check network error estate_id=%s service_key=%s",
            estate_id,
            service_key,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to verify service entitlement.",
        ) from exc

    data = response.json() if response.content else {}
    if not isinstance(data, dict) or not data.get("allowed"):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Estate is not entitled to '{service_key}' "
                f"(limit={(data or {}).get('limit')})."
            ),
        )
    return data


async def require_service_entitlement(
    revenue_base_url: str,
    *,
    estate_id: str | None,
    service_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Require an estate and that it is entitled to ``service_key``.

    Raises:
        HTTPException: 403 when ``estate_id`` is missing or not allowed;
            404 when the key is unknown; 502 when revenue-service fails.
    """
    if not estate_id:
        raise HTTPException(
            status_code=403,
            detail="Estate is required to use this feature.",
        )
    return await check_service_entitlement(
        revenue_base_url,
        estate_id=str(estate_id),
        service_key=service_key,
        client=client,
    )


async def resolve_retention_from_date(
    revenue_base_url: str,
    *,
    estate_id: str,
    service_key: str,
    from_date: datetime | None,
    client: httpx.AsyncClient | None = None,
) -> datetime:
    """
    Clamp ``from_date`` to the catalog retention window.

    Paid tiers use the entitled ``duration_days`` limit. Access (or any
    estate without a positive limit) uses
    ``EXTENDED_HISTORICAL_RECORD_DEFAULT_DAYS``.
    """
    result = await fetch_service_entitlement(
        revenue_base_url,
        estate_id=estate_id,
        service_key=service_key,
        client=client,
    )
    try:
        limit_days = int((result or {}).get("limit") or 0)
    except (TypeError, ValueError):
        limit_days = 0
    if not (result or {}).get("allowed") or limit_days <= 0:
        limit_days = settings.EXTENDED_HISTORICAL_RECORD_DEFAULT_DAYS

    earliest = datetime.now(tz=timezone.utc) - timedelta(days=limit_days)
    if from_date is None:
        return earliest
    if from_date.tzinfo is None:
        from_date = from_date.replace(tzinfo=timezone.utc)
    return max(from_date, earliest)


async def fetch_seat_limit(
    revenue_base_url: str,
    *,
    estate_id: str,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """
    Fetch ``max_active_users`` check payload (does not require allowed=true).

    Returns:
        Response dict, or None when revenue-service is unreachable.
    """
    return await fetch_service_entitlement(
        revenue_base_url,
        estate_id=estate_id,
        service_key=settings.MAX_ACTIVE_USERS_KEY,
        client=client,
    )


async def assert_seat_available(
    revenue_base_url: str,
    *,
    estate_id: str,
    current_active_users: int,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    """
    Enforce covered seat / ``max_active_users`` before registering a user.

    When revenue-service is down or the catalog key has no positive limit
    (typical Access / unseeded), registration is allowed. When a positive
    limit is present, ``current_active_users >= limit`` raises 403.

    Raises:
        HTTPException: 403 when the estate is at or over its seat limit.
    """
    result = await fetch_seat_limit(
        revenue_base_url,
        estate_id=estate_id,
        client=client,
    )
    if result is None:
        logger.warning(
            "Skipping seat enforcement (revenue unavailable) estate_id=%s",
            estate_id,
        )
        return None

    raw_limit = result.get("limit")
    if raw_limit is None and result.get("covered_users") is not None:
        raw_limit = result.get("covered_users")
    try:
        limit = int(raw_limit) if raw_limit is not None else 0
    except (TypeError, ValueError):
        limit = 0

    if limit <= 0:
        return result

    if current_active_users >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Estate has reached its active user seat limit ({limit}). "
                "Add seats or deactivate users before registering more."
            ),
        )
    return result
