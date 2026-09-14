"""Revenue-service AI feature entitlement checks."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from gatepass_entitlement.config import settings
from gatepass_entitlement.exceptions import EntitlementDeniedError
from gatepass_entitlement.http import (
    error_detail,
    get_json,
    join_url,
    passthrough_status,
)

logger = logging.getLogger(__name__)

_CHECK_PATH = "api/v1/ai-features/check"


async def check_ai_feature_allowed(
    revenue_base_url: str,
    *,
    estate_id: UUID | str,
    feature_key: str,
    client: httpx.AsyncClient | None = None,
    auth_token: str | None = None,
    allow_security: bool = False,
) -> bool:
    """
    Return whether ``estate_id`` may run ``feature_key`` per revenue-service.

    Calls ``GET /api/v1/ai-features/check``. ``allow_security=True``
    lets security check (gate validate → analyze). Default is
    admin-only. Fail-closed on transport errors.

    Raises:
        EntitlementDeniedError: 401 when the forwarded token is
            rejected; 403 when the feature is not allowed or the
            caller is not a member; 404 when the key is unknown;
            502 on revenue-service failures.
    """
    url = join_url(revenue_base_url, _CHECK_PATH)
    params = {
        "estate_id": str(estate_id),
        "feature_key": feature_key,
        "allow_security": "true" if allow_security else "false",
    }
    try:
        response = await get_json(
            url, params, client=client, auth_token=auth_token
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = passthrough_status(exc)
        if status_code == 404:
            raise EntitlementDeniedError(
                f"Unknown AI feature_key '{feature_key}'.",
                status_code=404,
            ) from exc
        if status_code in (401, 403):
            raise EntitlementDeniedError(
                error_detail(exc, "Not authorized."),
                status_code=status_code,
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
    revenue_base_url: str,
    *,
    estate_id: UUID | str,
    feature_key: str,
    client: httpx.AsyncClient | None = None,
    auth_token: str | None = None,
    allow_security: bool = False,
) -> bool:
    """Return whether the estate may use ``feature_key``; False on 403/404."""
    try:
        return await check_ai_feature_allowed(
            revenue_base_url,
            estate_id=estate_id,
            feature_key=feature_key,
            client=client,
            auth_token=auth_token,
            allow_security=allow_security,
        )
    except EntitlementDeniedError as exc:
        if exc.status_code in (403, 404):
            return False
        raise


async def resolve_incident_entitlements(
    revenue_base_url: str,
    *,
    estate_id: UUID | str,
    client: httpx.AsyncClient | None = None,
    auth_token: str | None = None,
    allow_security: bool = False,
) -> tuple[bool, bool, bool]:
    """
    Return ``(result_page, inhouse, llm)`` for incident result-page access.

    ``incident_report_summary_tier_1`` is result-page only. Tier 2 is
    in-house topic modelling. Tier 3 is the LLM narrative and includes
    tier 2. Higher summary grants also unlock the result page.
    """
    llm_ok = await is_ai_feature_allowed(
        revenue_base_url,
        estate_id=estate_id,
        feature_key=settings.INCIDENT_REPORT_SUMMARY_TIER_3_KEY,
        client=client,
        auth_token=auth_token,
        allow_security=allow_security,
    )
    inhouse_ok = llm_ok or await is_ai_feature_allowed(
        revenue_base_url,
        estate_id=estate_id,
        feature_key=settings.INCIDENT_REPORT_SUMMARY_TIER_2_KEY,
        client=client,
        auth_token=auth_token,
        allow_security=allow_security,
    )
    page_ok = inhouse_ok or await is_ai_feature_allowed(
        revenue_base_url,
        estate_id=estate_id,
        feature_key=settings.INCIDENT_REPORT_SUMMARY_TIER_1_KEY,
        client=client,
        auth_token=auth_token,
        allow_security=allow_security,
    )
    return page_ok, inhouse_ok, llm_ok
