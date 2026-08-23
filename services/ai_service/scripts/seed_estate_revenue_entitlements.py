#!/usr/bin/env python3
"""
Seed (or reverse) revenue catalog pricing + a Sentinel grant for one estate.

Creates (if missing):
  - service_catalog rows used by Phase 1 pricing
  - ai_feature row for anomaly detection
  - feature_unit_price rows (NG/NGN by default, or the estate's country)
  - active Sentinel estate_subscription + installed anomaly estate_ai_feature

Paste the estate UUID below, then run from ``services/ai_service``::

    python scripts/seed_estate_revenue_entitlements.py

Toggle ``main()`` between ``seed`` and ``reverse``.
Talks to db-service (default ``http://localhost:9032/``).

Note: ``reverse`` also removes the global catalog / AI / price rows for the
keys this script owns (after deleting estate grants/subscriptions).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

if "DB_SERVICE_URL" not in os.environ:
    os.environ["DB_SERVICE_URL"] = "http://localhost:9032/"

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402

TIER_SLUG = "sentinel"
AI_FEATURE_KEY = "visitor_resident_anomaly_detection"

DEFAULT_COUNTRY = "NG"
DEFAULT_CURRENCY = "NGN"

# Slim Phase 1 catalog + illustrative NG prices (matches alembic seed intent).
SERVICE_SEEDS: list[dict] = [
    {
        "service_key": "administrative_fee",
        "name": "Administrative Fee",
        "limit_type": "boolean",
        "feature_unit_price": 700,
    },
    {
        "service_key": "visitor_log_retention_days",
        "name": "Visitor Log Retention Days",
        "limit_type": "duration_days",
        "feature_unit_price": 400,
    },
    {
        "service_key": "resident_log_retention_days",
        "name": "Resident Log Retention Days",
        "limit_type": "duration_days",
        "feature_unit_price": 400,
    },
]
AI_SEEDS: list[dict] = [
    {
        "feature_key": AI_FEATURE_KEY,
        "name": "Visitor/Resident Anomaly Detection",
        "is_free": False,
        "feature_unit_price": 500,
    },
]


def _url(path: str) -> str:
    return f"{settings.DB_SERVICE_URL.rstrip('/')}/{path.lstrip('/')}"


async def _search_items(
    client: httpx.AsyncClient, path: str, params: dict
) -> list[dict]:
    response = await client.get(_url(path), params=params)
    response.raise_for_status()
    return (response.json() or {}).get("items") or []


async def _first_item(
    client: httpx.AsyncClient, path: str, params: dict
) -> dict:
    items = await _search_items(client, path, params)
    if not items:
        raise SystemExit(f"No rows for {path} params={params}")
    return items[0]


async def _delete_all(
    client: httpx.AsyncClient, search_path: str, params: dict
) -> int:
    items = await _search_items(client, search_path, params)
    base = search_path.removesuffix("/search")
    for item in items:
        delete_resp = await client.delete(f"{_url(base)}/{item['id']}")
        delete_resp.raise_for_status()
        print(f"Deleted {base} id={item['id']}")
    return len(items)


async def _get_or_create_service(
    client: httpx.AsyncClient, spec: dict
) -> dict:
    existing = await _search_items(
        client,
        "api/v1/revenue/servicecatalog/search",
        {"service_key": spec["service_key"], "limit": 1},
    )
    if existing:
        print(
            f"Reusing service_catalog {spec['service_key']} id={existing[0]['id']}"
        )
        return existing[0]
    response = await client.post(
        _url("api/v1/revenue/servicecatalog"),
        json={
            "service_key": spec["service_key"],
            "name": spec["name"],
            "description": None,
            "limit_type": spec["limit_type"],
            "is_active": True,
        },
    )
    response.raise_for_status()
    created = response.json()
    print(f"Created service_catalog {spec['service_key']} id={created['id']}")
    return created


async def _get_or_create_ai_feature(
    client: httpx.AsyncClient, spec: dict
) -> dict:
    existing = await _search_items(
        client,
        "api/v1/revenue/aifeature/search",
        {"feature_key": spec["feature_key"], "limit": 1},
    )
    if existing:
        print(
            f"Reusing ai_feature {spec['feature_key']} id={existing[0]['id']}"
        )
        return existing[0]
    response = await client.post(
        _url("api/v1/revenue/aifeature"),
        json={
            "feature_key": spec["feature_key"],
            "name": spec["name"],
            "description": None,
            "is_free": bool(spec["is_free"]),
            "is_active": True,
        },
    )
    response.raise_for_status()
    created = response.json()
    print(f"Created ai_feature {spec['feature_key']} id={created['id']}")
    return created


async def _get_or_create_service_price(
    client: httpx.AsyncClient,
    *,
    country_code: str,
    currency_code: str,
    service: dict,
    amount: float | int,
) -> dict:
    existing = await _search_items(
        client,
        "api/v1/revenue/featureunitprice/search",
        {
            "country_code": country_code,
            "service_catalog_id": str(service["id"]),
            "feature_kind": "service",
            "is_active": True,
            "limit": 1,
        },
    )
    if existing:
        print(
            f"Reusing feature_unit_price service={service['service_key']} "
            f"id={existing[0]['id']}"
        )
        return existing[0]
    response = await client.post(
        _url("api/v1/revenue/featureunitprice"),
        json={
            "country_code": country_code,
            "currency_code": currency_code,
            "feature_kind": "service",
            "service_catalog_id": str(service["id"]),
            "ai_feature_id": None,
            "feature_unit_price": amount,
            "is_active": True,
        },
    )
    response.raise_for_status()
    created = response.json()
    print(
        f"Created feature_unit_price service={service['service_key']} "
        f"id={created['id']} amount={amount}"
    )
    return created


async def _get_or_create_ai_price(
    client: httpx.AsyncClient,
    *,
    country_code: str,
    currency_code: str,
    feature: dict,
    amount: float | int,
) -> dict:
    existing = await _search_items(
        client,
        "api/v1/revenue/featureunitprice/search",
        {
            "country_code": country_code,
            "ai_feature_id": str(feature["id"]),
            "feature_kind": "ai",
            "is_active": True,
            "limit": 1,
        },
    )
    if existing:
        print(
            f"Reusing feature_unit_price ai={feature['feature_key']} "
            f"id={existing[0]['id']}"
        )
        return existing[0]
    response = await client.post(
        _url("api/v1/revenue/featureunitprice"),
        json={
            "country_code": country_code,
            "currency_code": currency_code,
            "feature_kind": "ai",
            "service_catalog_id": None,
            "ai_feature_id": str(feature["id"]),
            "feature_unit_price": amount,
            "is_active": True,
        },
    )
    response.raise_for_status()
    created = response.json()
    print(
        f"Created feature_unit_price ai={feature['feature_key']} "
        f"id={created['id']} amount={amount}"
    )
    return created


async def _resolve_country_currency(
    client: httpx.AsyncClient, estate_id: str
) -> tuple[str, str]:
    response = await client.get(
        _url(f"api/v1/userprofile/estates/{estate_id}")
    )
    if response.status_code == 404:
        raise SystemExit(f"Estate not found: {estate_id}")
    response.raise_for_status()
    estate = response.json() or {}
    country = (estate.get("country") or DEFAULT_COUNTRY).upper()
    # Script only seeds NG prices today; other countries fall back to NG/NGN
    # amounts with the estate country code so checkout can still join.
    currency = DEFAULT_CURRENCY if country == "NG" else DEFAULT_CURRENCY
    if not estate.get("country"):
        print(f"Estate has no country; using {country}/{currency} for prices")
    return country, currency


async def seed_catalog_and_prices(
    client: httpx.AsyncClient, *, country_code: str, currency_code: str
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Ensure service_catalog, ai_feature, and feature_unit_price rows exist."""
    services: dict[str, dict] = {}
    for spec in SERVICE_SEEDS:
        service = await _get_or_create_service(client, spec)
        services[spec["service_key"]] = service
        await _get_or_create_service_price(
            client,
            country_code=country_code,
            currency_code=currency_code,
            service=service,
            amount=spec["feature_unit_price"],
        )

    features: dict[str, dict] = {}
    for spec in AI_SEEDS:
        feature = await _get_or_create_ai_feature(client, spec)
        features[spec["feature_key"]] = feature
        await _get_or_create_ai_price(
            client,
            country_code=country_code,
            currency_code=currency_code,
            feature=feature,
            amount=spec["feature_unit_price"],
        )
    return services, features


async def seed(estate_id: str) -> None:
    """Seed catalog prices + Sentinel subscription + anomaly AI grant."""
    now = datetime.now(tz=timezone.utc)
    async with httpx.AsyncClient(timeout=30.0) as client:
        country, currency = await _resolve_country_currency(client, estate_id)
        _services, features = await seed_catalog_and_prices(
            client, country_code=country, currency_code=currency
        )

        tier = await _first_item(
            client,
            "api/v1/revenue/subscriptiontier/search",
            {"slug": TIER_SLUG, "limit": 1},
        )
        feature = features[AI_FEATURE_KEY]

        sub_resp = await client.post(
            _url("api/v1/revenue/estatesubscription"),
            json={
                "estate_id": estate_id,
                "tier_id": tier["id"],
                "status": "active",
                "period_start": now.isoformat(),
                "period_end": (now + timedelta(days=30)).isoformat(),
                "auto_renew": True,
                "covered_users": 1,
            },
        )
        sub_resp.raise_for_status()
        subscription_id = sub_resp.json()["id"]
        print(f"Created estate_subscription id={subscription_id}")

        grant_resp = await client.post(
            _url("api/v1/revenue/estateaifeature"),
            json={
                "estate_id": estate_id,
                "ai_feature_id": feature["id"],
                "source": "subscription_tier",
                "estate_subscription_id": subscription_id,
                "is_installed": True,
                "status": "active",
                "is_free": False,
                "auto_renew": True,
                "starts_at": now.isoformat(),
                "expires_at": (now + timedelta(days=30)).isoformat(),
            },
        )
        grant_resp.raise_for_status()
        print(f"Created estate_ai_feature id={grant_resp.json()['id']}")


async def reverse_catalog_and_prices(
    client: httpx.AsyncClient, *, country_code: str
) -> None:
    """
    Remove feature_unit_price rows for this script's keys/country, then the
    associated service_catalog and ai_feature definitions.
    """
    # Prices first (FK dependents of catalog / AI rows).
    for spec in SERVICE_SEEDS:
        services = await _search_items(
            client,
            "api/v1/revenue/servicecatalog/search",
            {"service_key": spec["service_key"], "limit": 1},
        )
        if not services:
            continue
        await _delete_all(
            client,
            "api/v1/revenue/featureunitprice/search",
            {
                "country_code": country_code,
                "service_catalog_id": str(services[0]["id"]),
                "feature_kind": "service",
                "limit": 50,
            },
        )

    for spec in AI_SEEDS:
        features = await _search_items(
            client,
            "api/v1/revenue/aifeature/search",
            {"feature_key": spec["feature_key"], "limit": 1},
        )
        if not features:
            continue
        await _delete_all(
            client,
            "api/v1/revenue/featureunitprice/search",
            {
                "country_code": country_code,
                "ai_feature_id": str(features[0]["id"]),
                "feature_kind": "ai",
                "limit": 50,
            },
        )

    for spec in SERVICE_SEEDS:
        await _delete_all(
            client,
            "api/v1/revenue/servicecatalog/search",
            {"service_key": spec["service_key"], "limit": 5},
        )
    for spec in AI_SEEDS:
        await _delete_all(
            client,
            "api/v1/revenue/aifeature/search",
            {"feature_key": spec["feature_key"], "limit": 5},
        )


async def reverse(estate_id: str) -> None:
    """
    Soft-delete estate grants/subscription, then catalog prices + associates.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        country, _currency = await _resolve_country_currency(client, estate_id)

        for path in (
            "api/v1/revenue/estateaifeature/search",
            "api/v1/revenue/estatesubscription/search",
        ):
            await _delete_all(
                client, path, {"estate_id": estate_id, "limit": 50}
            )

        await reverse_catalog_and_prices(client, country_code=country)
        print(
            f"Reversed entitlements + {country} prices/associates "
            f"for estate_id={estate_id}"
        )


async def main() -> None:
    # Paste estate UUID here:
    estate_id = "6eb0c18d-5505-4601-a211-1584b6a5bc31"

    await seed(estate_id)
    # await reverse(estate_id)


if __name__ == "__main__":
    asyncio.run(main())
