"""Revenue-service client for AI feature entitlement checks."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import EntitlementDeniedError

logger = logging.getLogger(__name__)

#: Seeded AI catalog key for visitor/resident anomaly detection.
ANOMALY_FEATURE_KEY = "visitor_resident_anomaly_detection"
#: Seeded AI catalog key for paid incident LLM summary.
INCIDENT_SUMMARY_FEATURE_KEY = "incident_summary_basic"
#: In-house formatted summary for a selected anomaly case.
ANOMALY_SUMMARY_TIER2_KEY = "visitor_resident_anomaly_detection_tier2"
#: LLM summary for a selected anomaly case (includes in-house).
ANOMALY_SUMMARY_TIER3_KEY = "visitor_resident_anomaly_detection_tier3"


def _revenue_url(settings: Settings, path: str) -> str:
    """Join ``REVENUE_SERVICE_URL`` with a relative API path."""
    base = settings.REVENUE_SERVICE_URL.rstrip("/") + "/"
    return base + path.lstrip("/")


async def check_ai_feature_allowed(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID | str,
    feature_key: str = ANOMALY_FEATURE_KEY,
) -> bool:
    """
    Return whether ``estate_id`` may run ``feature_key`` per revenue-service.

    Calls ``GET /api/v1/ai-features/check``. Fail-closed on transport errors.

    Args:
        client: Shared httpx client.
        settings: AI service settings (needs ``REVENUE_SERVICE_URL``).
        estate_id: Estate UUID.
        feature_key: AI catalog feature key.

    Returns:
        True when revenue-service reports ``allowed``.

    Raises:
        EntitlementDeniedError: When the feature is not allowed (403).
        EntitlementDeniedError: On revenue-service failures (502/fail-closed).
    """
    url = _revenue_url(settings, "api/v1/ai-features/check")
    params = {
        "estate_id": str(estate_id),
        "feature_key": feature_key,
    }
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise EntitlementDeniedError(
                f"Unknown AI feature_key '{feature_key}'.",
                status_code=404,
            ) from exc
        logger.exception(
            "AI feature check HTTP error estate_id=%s feature_key=%s "
            "status=%s",
            estate_id,
            feature_key,
            exc.response.status_code,
        )
        raise EntitlementDeniedError(
            "Unable to verify AI feature entitlement.",
            status_code=502,
        ) from exc
    except httpx.RequestError as exc:
        logger.exception(
            "AI feature check network error estate_id=%s feature_key=%s",
            estate_id,
            feature_key,
        )
        raise EntitlementDeniedError(
            "Unable to verify AI feature entitlement.",
            status_code=502,
        ) from exc

    data = response.json() if response.content else {}
    if not isinstance(data, dict) or not data.get("allowed"):
        raise EntitlementDeniedError(
            f"Estate is not entitled to AI feature '{feature_key}'.",
            status_code=403,
        )
    return True


async def is_ai_feature_allowed(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    estate_id: UUID | str,
    feature_key: str,
) -> bool:
    """Return whether the estate may use ``feature_key``; False on 403/404."""
    try:
        return await check_ai_feature_allowed(
            client,
            settings,
            estate_id=estate_id,
            feature_key=feature_key,
        )
    except EntitlementDeniedError as exc:
        if exc.status_code in (403, 404):
            return False
        raise
