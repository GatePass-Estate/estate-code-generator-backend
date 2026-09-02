#!/usr/bin/env python3
"""
Seed case-summary AI features and grant them to one estate.

Creates (if missing):
  - ai_feature rows for visitor_resident_anomaly_detection_tier2/tier3
  - feature_unit_price rows (NG/NGN by default, or the estate's country)
  - estate_ai_feature grants linked to the estate's active subscription

Does not touch catalog rows or grants owned by
``seed_estate_revenue_entitlements.py``.

Paste the estate UUID below, then run from ``services/ai_service``::

    python scripts/seed_anomaly_case_summary_entitlements.py

Toggle ``main()`` between ``seed`` and ``reverse``.
Talks to db-service (default ``http://localhost:9032/``).
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

DEFAULT_COUNTRY = "NG"
DEFAULT_CURRENCY = "NGN"

AI_SEEDS: list[dict] = [
    {
        "feature_key": "visitor_resident_anomaly_detection_tier2",
        "name": "Visitor/Resident Anomaly Case Summary (In-house)",
        "description": (
            "Formatted executive summary and detailed insight "
            "from a stored prediction result."
        ),
        "is_free": False,
        "feature_unit_price": 500,
    },
    {
        "feature_key": "visitor_resident_anomaly_detection_tier3",
        "name": "Visitor/Resident Anomaly Case Summary (LLM)",
        "description": (
            "Includes in-house summary plus a third-party LLM "
            "narrative with deeper operational insight."
        ),
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
    currency = DEFAULT_CURRENCY
    if not estate.get("country"):
        print(f"Estate has no country; using {country}/{currency} for prices")
    return country, currency


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
            "description": spec.get("description"),
            "is_free": bool(spec["is_free"]),
            "is_active": True,
        },
    )
    response.raise_for_status()
    created = response.json() or {}
    # POST /aifeature returns id + created_at only.
    created["feature_key"] = spec["feature_key"]
    print(f"Created ai_feature {spec['feature_key']} id={created['id']}")
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


async def _active_subscription(
    client: httpx.AsyncClient, estate_id: str
) -> dict:
    items = await _search_items(
        client,
        "api/v1/revenue/estatesubscription/search",
        {"estate_id": estate_id, "status": "active", "limit": 1},
    )
    if not items:
        raise SystemExit(
            f"No active estate_subscription for estate_id={estate_id}. "
            "Run seed_estate_revenue_entitlements.py first."
        )
    print(f"Using estate_subscription id={items[0]['id']}")
    return items[0]


async def _get_or_create_ai_grant(
    client: httpx.AsyncClient,
    *,
    estate_id: str,
    feature: dict,
    subscription_id: str,
    now: datetime,
) -> dict:
    existing = await _search_items(
        client,
        "api/v1/revenue/estateaifeature/search",
        {
            "estate_id": estate_id,
            "ai_feature_id": str(feature["id"]),
            "limit": 1,
        },
    )
    if existing:
        print(
            f"Reusing estate_ai_feature {feature['feature_key']} "
            f"id={existing[0]['id']}"
        )
        return existing[0]
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
    created = grant_resp.json()
    print(
        f"Created estate_ai_feature {feature['feature_key']} "
        f"id={created['id']}"
    )
    return created


async def seed(estate_id: str) -> None:
    """Seed case-summary AI features, prices, and estate grants."""
    now = datetime.now(tz=timezone.utc)
    async with httpx.AsyncClient(timeout=30.0) as client:
        country, currency = await _resolve_country_currency(client, estate_id)
        subscription = await _active_subscription(client, estate_id)
        for spec in AI_SEEDS:
            feature = await _get_or_create_ai_feature(client, spec)
            await _get_or_create_ai_price(
                client,
                country_code=country,
                currency_code=currency,
                feature=feature,
                amount=spec["feature_unit_price"],
            )
            await _get_or_create_ai_grant(
                client,
                estate_id=estate_id,
                feature=feature,
                subscription_id=subscription["id"],
                now=now,
            )


async def reverse(estate_id: str) -> None:
    """Remove this script's grants, prices, and ai_feature rows only."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        country, _currency = await _resolve_country_currency(client, estate_id)
        for spec in AI_SEEDS:
            features = await _search_items(
                client,
                "api/v1/revenue/aifeature/search",
                {"feature_key": spec["feature_key"], "limit": 1},
            )
            if not features:
                continue
            feature_id = str(features[0]["id"])
            await _delete_all(
                client,
                "api/v1/revenue/estateaifeature/search",
                {
                    "estate_id": estate_id,
                    "ai_feature_id": feature_id,
                    "limit": 50,
                },
            )
            await _delete_all(
                client,
                "api/v1/revenue/featureunitprice/search",
                {
                    "country_code": country,
                    "ai_feature_id": feature_id,
                    "feature_kind": "ai",
                    "limit": 50,
                },
            )
            await _delete_all(
                client,
                "api/v1/revenue/aifeature/search",
                {"feature_key": spec["feature_key"], "limit": 5},
            )
        print(
            f"Reversed case-summary features/grants for estate_id={estate_id}"
        )


async def main() -> None:
    # Paste estate UUID here:
    estate_id = "6eb0c18d-5505-4601-a211-1584b6a5bc31"

    await seed(estate_id)
    # await reverse(estate_id)


if __name__ == "__main__":
    asyncio.run(main())
