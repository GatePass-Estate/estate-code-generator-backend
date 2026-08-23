#!/usr/bin/env python3
"""
Seed (or reverse) a Sentinel subscription + anomaly AI grant for one estate.

Paste the estate UUID below, then run from ``services/ai_service``::

    python scripts/seed_estate_revenue_entitlements.py

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

TIER_SLUG = "sentinel"
AI_FEATURE_KEY = "visitor_resident_anomaly_detection"


def _url(path: str) -> str:
    return f"{settings.DB_SERVICE_URL.rstrip('/')}/{path.lstrip('/')}"


async def _first_item(
    client: httpx.AsyncClient, path: str, params: dict
) -> dict:
    response = await client.get(_url(path), params=params)
    response.raise_for_status()
    items = (response.json() or {}).get("items") or []
    if not items:
        raise SystemExit(f"No rows for {path} params={params}")
    return items[0]


async def seed(estate_id: str) -> None:
    """Create active Sentinel subscription + installed anomaly AI grant."""
    now = datetime.now(tz=timezone.utc)
    async with httpx.AsyncClient(timeout=30.0) as client:
        tier = await _first_item(
            client,
            "api/v1/revenue/subscriptiontier/search",
            {"slug": TIER_SLUG, "limit": 1},
        )
        feature = await _first_item(
            client,
            "api/v1/revenue/aifeature/search",
            {"feature_key": AI_FEATURE_KEY, "limit": 1},
        )

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


async def reverse(estate_id: str) -> None:
    """Soft-delete subscription and AI grants for the estate."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for path in (
            "api/v1/revenue/estateaifeature/search",
            "api/v1/revenue/estatesubscription/search",
        ):
            response = await client.get(
                _url(path),
                params={"estate_id": estate_id, "limit": 50},
            )
            response.raise_for_status()
            items = (response.json() or {}).get("items") or []
            base = path.removesuffix("/search")
            for item in items:
                delete_resp = await client.delete(f"{_url(base)}/{item['id']}")
                delete_resp.raise_for_status()
                print(f"Deleted {base} id={item['id']}")
        print(f"Reversed entitlements for estate_id={estate_id}")


async def main() -> None:
    # Paste estate UUID here:
    estate_id = "6eb0c18d-5505-4601-a211-1584b6a5bc31"

    await seed(estate_id)
    # await reverse(estate_id)


if __name__ == "__main__":
    asyncio.run(main())
