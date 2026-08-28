"""Revenue-service client for seat / entitlement checks."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)

MAX_ACTIVE_USERS_KEY = "max_active_users"


def _check_url() -> str:
    base = (settings.REVENUE_SERVICE_URL or "").rstrip("/") + "/"
    return f"{base}api/v1/entitlements/check"


async def fetch_seat_limit(
    ahttp_client: AsyncHttpHandler,
    *,
    estate_id: str,
) -> dict | None:
    """
    Fetch ``max_active_users`` check payload (does not require allowed=true).

    Returns:
        Response dict, or None when revenue-service is unreachable / unknown key.
    """
    params = {"estate_id": estate_id, "service_key": MAX_ACTIVE_USERS_KEY}
    try:
        response = await ahttp_client.async_get(_check_url(), params=params)
    except Exception:
        logger.exception(
            "Seat limit lookup failed estate_id=%s",
            estate_id,
        )
        return None
    if not isinstance(response, dict):
        return None
    return response


async def assert_seat_available(
    ahttp_client: AsyncHttpHandler,
    *,
    estate_id: str,
    current_active_users: int,
) -> dict | None:
    """
    Enforce covered seat / ``max_active_users`` before registering a user.

    When revenue-service is down or the catalog key has no positive limit
    (typical Access / unseeded), registration is allowed. When a positive
    limit is present, ``current_active_users >= limit`` raises 403.

    Raises:
        HTTPException: 403 when the estate is at or over its seat limit.
    """
    result = await fetch_seat_limit(ahttp_client, estate_id=estate_id)
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
        # No seat cap configured on this plan.
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
