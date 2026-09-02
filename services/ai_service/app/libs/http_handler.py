"""Async HTTP client helpers for outbound service calls."""

from typing import Any, AsyncGenerator

import httpx
from fastapi import HTTPException


class AsyncHttpHandler:
    """Thin httpx wrapper. Returns JSON, or None on 404."""

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_data: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any | None:
        """Send an HTTP request and return decoded JSON, or None on 404."""
        kwargs: dict[str, Any] = {"headers": headers}
        if params is not None:
            kwargs["params"] = params
        if json_data is not None:
            kwargs["json"] = json_data
        if data is not None:
            kwargs["data"] = data
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    return None
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Upstream returned HTTP {exc.response.status_code} "
                        f"for {method} {url}"
                    ),
                ) from exc
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Upstream service unavailable for {method} {url}",
                ) from exc

    async def async_get(
        self, url: str, params: dict = None, headers: dict = None
    ) -> Any | None:
        """GET ``url`` and return JSON, or None on 404."""
        return await self._request("GET", url, params=params, headers=headers)

    async def async_post(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ) -> Any | None:
        """POST ``url`` and return JSON, or None on 404."""
        return await self._request(
            "POST", url, data=data, json_data=json_data, headers=headers
        )

    async def async_patch(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ) -> Any | None:
        """PATCH ``url`` and return JSON, or None on 404."""
        return await self._request(
            "PATCH", url, data=data, json_data=json_data, headers=headers
        )


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """Yield the shared AsyncHttpHandler for FastAPI dependency injection."""
    yield handler
