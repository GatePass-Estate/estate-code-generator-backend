"""Revenue-service client for service-catalog entitlement checks."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)

VISITOR_LOG_RETENTION_KEY = "visitor_log_retention_days"
RESIDENT_LOG_RETENTION_KEY = "resident_log_retention_days"


def _check_url() -> str:
    base = (settings.REVENUE_SERVICE_URL or "").rstrip("/") + "/"
    return f"{base}api/v1/entitlements/check"


async def check_entitlement(
    ahttp_client: AsyncHttpHandler,
    *,
    estate_id: str,
    service_key: str,
) -> dict:
    """
    Call revenue-service entitlement check for one service_key.

    Returns:
        Parsed JSON body from revenue-service.

    Raises:
        HTTPException: 403 when not allowed; 404 when unknown key;
            502 when revenue-service fails.
    """
    params = {"estate_id": estate_id, "service_key": service_key}
    try:
        response = await ahttp_client.async_get(_check_url(), params=params)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown service_key '{service_key}'.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Entitlement check failed estate_id=%s service_key=%s",
            estate_id,
            service_key,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to verify service entitlement.",
        ) from exc
    if not response or not response.get("allowed"):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Estate is not entitled to '{service_key}' "
                f"(limit={(response or {}).get('limit')})."
            ),
        )
    return response


async def resolve_retention_from_date(
    ahttp_client: AsyncHttpHandler,
    *,
    estate_id: str,
    service_key: str,
    from_date: datetime | None,
) -> datetime:
    """
    Enforce catalog retention days and return the effective from_date floor.

    Raises:
        HTTPException: 403 when the estate is not entitled (limit <= 0).
    """
    result = await check_entitlement(
        ahttp_client,
        estate_id=estate_id,
        service_key=service_key,
    )
    try:
        limit_days = int(result.get("limit") or 0)
    except (TypeError, ValueError):
        limit_days = 0
    if limit_days <= 0:
        raise HTTPException(
            status_code=403,
            detail=f"Estate is not entitled to '{service_key}'.",
        )

    earliest = datetime.now(tz=timezone.utc) - timedelta(days=limit_days)
    if from_date is None:
        return earliest
    if from_date.tzinfo is None:
        from_date = from_date.replace(tzinfo=timezone.utc)
    return max(from_date, earliest)
