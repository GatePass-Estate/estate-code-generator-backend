"""HTTP helpers for revenue-service entitlement endpoints."""

from __future__ import annotations

from collections.abc import Mapping

import httpx

_TIMEOUT = httpx.Timeout(15.0)


def join_url(base_url: str, path: str) -> str:
    """Join ``base_url`` with a relative API path."""
    base = (base_url or "").rstrip("/") + "/"
    return base + path.lstrip("/")


def _headers(auth_token: str | None = None) -> dict[str, str]:
    """Build headers for a revenue-service entitlement GET."""
    if not auth_token:
        return {}
    return {"Authorization": f"Bearer {auth_token}"}


async def get_json(
    url: str,
    params: Mapping[str, str],
    *,
    client: httpx.AsyncClient | None = None,
    auth_token: str | None = None,
) -> httpx.Response:
    """GET ``url`` and return the response without raising."""
    headers = _headers(auth_token)
    if client is not None:
        return await client.get(url, params=dict(params), headers=headers)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as owned:
        return await owned.get(url, params=dict(params), headers=headers)
