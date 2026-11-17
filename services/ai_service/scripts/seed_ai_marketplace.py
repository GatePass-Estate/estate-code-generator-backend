#!/usr/bin/env python3
"""
Seed (or reverse) AI marketplace catalog + ratings via db-service.

Creates (if missing):
  - one ``ai_marketplace_feature`` whose single tier points at the existing
    ``visitor_resident_anomaly_detection`` ai_feature
  - ratings across scores 1–5 (more than 5 per score so summary sampling
    can be verified)

Paste nothing estate-specific; catalog rows are global.

Run from ``services/ai_service``::

    python scripts/seed_ai_marketplace.py

Toggle ``main()`` between ``seed`` and ``reverse``.
Talks to db-service (default ``http://localhost:9032/``).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

if "DB_SERVICE_URL" not in os.environ:
    os.environ["DB_SERVICE_URL"] = "http://localhost:9032/"

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402

AI_FEATURE_KEY = "visitor_resident_anomaly_detection"
PRODUCT_NAME = "Visitor/Resident Anomaly Detection"
PRODUCT_CATEGORY = "Anomaly Detection"
PRODUCT_DESCRIPTION = (
    "Flag unusual visitor and resident access patterns using spatial and "
    "temporal detectors."
)
TIER_NAME = "standard"

# Per-score counts: each > 5 so /summary returns at most 5 samples per level.
RATINGS_PER_SCORE = {1: 6, 2: 6, 3: 7, 4: 6, 5: 8}

MARKETPLACE = "api/v1/revenue/aimarketplacefeature"
RATINGS = "api/v1/revenue/aimarketplacefeaturerating"
AI_FEATURE = "api/v1/revenue/aifeature"


def _url(path: str) -> str:
    """Join ``path`` onto the configured db-service base URL."""
    return f"{settings.DB_SERVICE_URL.rstrip('/')}/{path.lstrip('/')}"


def _seed_comment(score: int, index: int) -> str | None:
    """Return a comment on odd indexes, otherwise None."""
    if index % 2 == 0:
        return None
    return f"Seed review: score {score} sample {index}"


async def _search_items(
    client: httpx.AsyncClient, path: str, params: dict
) -> list[dict]:
    """GET a db-service search endpoint and return ``items``."""
    response = await client.get(_url(path), params=params)
    response.raise_for_status()
    return (response.json() or {}).get("items") or []


async def _first_item(
    client: httpx.AsyncClient, path: str, params: dict
) -> dict:
    """Return the first search hit, or exit if none match."""
    items = await _search_items(client, path, params)
    if not items:
        raise SystemExit(f"No rows for {path} params={params}")
    return items[0]


async def _delete_all(
    client: httpx.AsyncClient, search_path: str, params: dict
) -> int:
    """Soft-delete every row returned by a search; return the count."""
    items = await _search_items(client, search_path, params)
    base = search_path.removesuffix("/search")
    for item in items:
        delete_resp = await client.delete(f"{_url(base)}/{item['id']}")
        delete_resp.raise_for_status()
        print(f"Deleted {base} id={item['id']}")
    return len(items)


async def _get_anomaly_feature(client: httpx.AsyncClient) -> dict:
    """Look up the existing visitor/resident anomaly ``ai_feature``."""
    return await _first_item(
        client,
        f"{AI_FEATURE}/search",
        {"feature_key": AI_FEATURE_KEY, "limit": 1},
    )


async def _get_or_create_product(
    client: httpx.AsyncClient, ai_feature_id: str
) -> dict:
    """Reuse or create the seeded marketplace parent product."""
    existing = await _search_items(
        client,
        f"{MARKETPLACE}/search",
        {"name": PRODUCT_NAME, "category": PRODUCT_CATEGORY, "limit": 1},
    )
    if existing:
        print(f"Reusing ai_marketplace_feature id={existing[0]['id']}")
        return existing[0]
    response = await client.post(
        _url(MARKETPLACE),
        json={
            "name": PRODUCT_NAME,
            "description": PRODUCT_DESCRIPTION,
            "category": PRODUCT_CATEGORY,
            "is_active": True,
            "tiers": [
                {"tier": TIER_NAME, "ai_feature_id": ai_feature_id},
            ],
        },
    )
    response.raise_for_status()
    created = response.json()
    print(f"Created ai_marketplace_feature id={created['id']}")
    return created


async def _get_or_create_rating(
    client: httpx.AsyncClient,
    *,
    product_id: str,
    user_id: str,
    score: int,
    comment: str | None,
) -> dict:
    """Reuse or create one rating for ``user_id`` on this product."""
    existing = await _search_items(
        client,
        f"{RATINGS}/search",
        {
            "ai_marketplace_feature_id": product_id,
            "user_id": user_id,
            "limit": 1,
        },
    )
    if existing:
        print(f"Reusing rating user={user_id} score={score}")
        return existing[0]
    response = await client.post(
        _url(RATINGS),
        json={
            "ai_marketplace_feature_id": product_id,
            "user_id": user_id,
            "score": score,
            "comment": comment,
        },
    )
    response.raise_for_status()
    created = response.json()
    print(
        f"Created rating id={created['id']} score={score} "
        f"comment={'yes' if comment else 'no'}"
    )
    return created


async def _print_summary(client: httpx.AsyncClient, product_id: str) -> None:
    """Print average rating and sample counts per score for a product."""
    response = await client.get(
        _url(f"{RATINGS}/summary"),
        params={"ai_marketplace_feature_id": product_id},
    )
    response.raise_for_status()
    items = (response.json() or {}).get("items") or []
    if not items:
        print("Summary returned no items")
        return
    row = items[0]
    samples = row.get("samples") or {}
    counts = {
        score: len(samples.get(str(score)) or []) for score in range(1, 6)
    }
    print(
        f"Summary rating={row.get('rating')} "
        f"count={row.get('rating_count')} "
        f"samples_per_score={counts}"
    )


async def seed() -> None:
    """Seed marketplace product + ratings that exercise summary sampling."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        feature = await _get_anomaly_feature(client)
        print(f"Linking to ai_feature {AI_FEATURE_KEY} id={feature['id']}")
        product = await _get_or_create_product(client, str(feature["id"]))
        product_id = str(product["id"])
        created = 0
        for score, n in RATINGS_PER_SCORE.items():
            for index in range(n):
                await _get_or_create_rating(
                    client,
                    product_id=product_id,
                    user_id=str(uuid4()),
                    score=score,
                    comment=_seed_comment(score, index),
                )
                created += 1
        print(f"Ensured {created} ratings for product id={product_id}")
        await _print_summary(client, product_id)


async def reverse() -> None:
    """Soft-delete seeded ratings, then the marketplace product."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        products = await _search_items(
            client,
            f"{MARKETPLACE}/search",
            {"name": PRODUCT_NAME, "category": PRODUCT_CATEGORY, "limit": 5},
        )
        for product in products:
            product_id = str(product["id"])
            deleted = await _delete_all(
                client,
                f"{RATINGS}/search",
                {
                    "ai_marketplace_feature_id": product_id,
                    "limit": 200,
                },
            )
            print(f"Deleted {deleted} ratings for product id={product_id}")
        await _delete_all(
            client,
            f"{MARKETPLACE}/search",
            {"name": PRODUCT_NAME, "category": PRODUCT_CATEGORY, "limit": 5},
        )
        print("Reversed AI marketplace seed rows")


async def main() -> None:
    """Run ``seed`` (swap to ``reverse`` to tear seeded rows down)."""
    await seed()
    # await reverse()


if __name__ == "__main__":
    asyncio.run(main())
