"""HTTP helpers for revenue-service entitlement endpoints."""

from __future__ import annotations

from collections.abc import Mapping

import httpx

_TIMEOUT = httpx.Timeout(15.0)


def join_url(base_url: str, path: str) -> str:
    """Join ``base_url`` with a relative API path."""
    base = (base_url or "").rstrip("/") + "/"
    return base + path.lstrip("/")


async def get_json(
    url: str,
    params: Mapping[str, str],
    *,
    client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    """GET ``url`` and return the response without raising."""
    if client is not None:
        return await client.get(url, params=dict(params))
    async with httpx.AsyncClient(timeout=_TIMEOUT) as owned:
        return await owned.get(url, params=dict(params))
