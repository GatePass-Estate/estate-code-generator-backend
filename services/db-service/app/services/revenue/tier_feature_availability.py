"""Build per-tier feature availability for subscription tier API responses."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.free_platform_features import (
    EXCLUDED_SERVICE_CATALOG_KEYS,
    FREE_PLATFORM_FEATURES,
)
from app.schemas.revenue.subscription_tier import (
    AiFeatureAvailabilityGroup,
    AiFeatureLabel,
    ServiceFeatureAvailabilityGroup,
    ServiceFeatureLabel,
)


def tier_dict_from_response_fields(
    *,
    slug: str,
    is_custom: bool,
    entitlements: dict | None,
    included_ai_features: list[str] | None,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "is_custom": is_custom,
        "entitlements": entitlements or {},
        "included_ai_features": list(included_ai_features or []),
    }


def tier_includes_paid_service(
    tier: dict[str, Any],
    *,
    service_key: str,
    limit_type: str,
) -> bool:
    """Return whether ``tier`` entitles the estate to a paid catalog service."""
    if tier.get("is_custom"):
        return True
    entitlements = tier.get("entitlements") or {}
    value = entitlements.get(service_key)
    if limit_type == "boolean":
        return value is True
    if limit_type in ("int", "count", "duration_days"):
        return isinstance(value, int) and value > 0
    return bool(value)


def tier_includes_ai_feature(tier: dict[str, Any], feature_key: str) -> bool:
    if tier.get("is_custom"):
        return True
    included = tier.get("included_ai_features") or []
    return feature_key in included


def build_tier_feature_availability(
    tier: dict[str, Any],
    *,
    service_catalog_rows: list[dict[str, str]],
    ai_feature_rows: list[dict[str, str]],
) -> tuple[
    ServiceFeatureAvailabilityGroup,
    ServiceFeatureAvailabilityGroup,
    AiFeatureAvailabilityGroup,
]:
    """
    For one tier, split catalog features into available vs unavailable lists.

    Free GPF features are always in ``available``. Custom tiers include all
    paid and AI catalog entries under ``available``.
    """
    free_available = [
        ServiceFeatureLabel(
            service_key=item["service_key"],
            label=item["label"],
        )
        for item in FREE_PLATFORM_FEATURES
    ]
    free = ServiceFeatureAvailabilityGroup(
        available=free_available,
        unavailable=[],
    )

    paid_available: list[ServiceFeatureLabel] = []
    paid_unavailable: list[ServiceFeatureLabel] = []
    for row in service_catalog_rows:
        key = row["service_key"]
        if key in EXCLUDED_SERVICE_CATALOG_KEYS:
            continue
        entry = ServiceFeatureLabel(service_key=key, label=row["name"])
        if tier_includes_paid_service(
            tier, service_key=key, limit_type=row["limit_type"]
        ):
            paid_available.append(entry)
        else:
            paid_unavailable.append(entry)

    ai_available: list[AiFeatureLabel] = []
    ai_unavailable: list[AiFeatureLabel] = []
    for row in ai_feature_rows:
        entry = AiFeatureLabel(
            feature_key=row["feature_key"],
            label=row["name"],
        )
        if tier_includes_ai_feature(tier, row["feature_key"]):
            ai_available.append(entry)
        else:
            ai_unavailable.append(entry)

    return (
        free,
        ServiceFeatureAvailabilityGroup(
            available=paid_available,
            unavailable=paid_unavailable,
        ),
        AiFeatureAvailabilityGroup(
            available=ai_available,
            unavailable=ai_unavailable,
        ),
    )


async def load_feature_catalog_rows(
    session: AsyncSession,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load active service_catalog and ai_feature rows for availability."""
    from sqlalchemy import select

    from app.models import AiFeature, ServiceCatalog

    svc_result = await session.execute(
        select(ServiceCatalog).where(
            ServiceCatalog.is_deleted == False,  # noqa: E712
            ServiceCatalog.is_active == True,  # noqa: E712
        )
    )
    service_rows = [
        {
            "service_key": r.service_key,
            "name": r.name,
            "limit_type": r.limit_type,
        }
        for r in svc_result.scalars().all()
        if r.service_key not in EXCLUDED_SERVICE_CATALOG_KEYS
    ]
    service_rows.sort(key=lambda r: r["service_key"])

    ai_result = await session.execute(
        select(AiFeature).where(
            AiFeature.is_deleted == False,  # noqa: E712
            AiFeature.is_active == True,  # noqa: E712
        )
    )
    ai_rows = [
        {"feature_key": r.feature_key, "name": r.name}
        for r in ai_result.scalars().all()
    ]
    ai_rows.sort(key=lambda r: r["feature_key"])

    return service_rows, ai_rows
