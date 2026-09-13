"""HTTP helpers for revenue-service entitlement endpoints."""

from __future__ import annotations

from collections.abc import Mapping

import httpx

_TIMEOUT = httpx.Timeout(15.0)
_PASSTHROUGH_STATUSES = frozenset({401, 403, 404})


def join_url(base_url: str, path: str) -> str:
    """Join ``base_url`` with a relative API path."""
    base = (base_url or "").rstrip("/") + "/"
    return base + path.lstrip("/")


def passthrough_status(exc: httpx.HTTPStatusError) -> int | None:
    """Return 401/403/404 so callers can keep revenue-service status codes."""
    code = exc.response.status_code
    return code if code in _PASSTHROUGH_STATUSES else None


def error_detail(exc: httpx.HTTPStatusError, fallback: str) -> str:
    """Return revenue-service ``detail`` when it is a string, else ``fallback``."""
    try:
        payload = exc.response.json()
    except ValueError:
        return fallback
    detail = payload.get("detail") if isinstance(payload, dict) else None
    return detail if isinstance(detail, str) and detail else fallback


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
