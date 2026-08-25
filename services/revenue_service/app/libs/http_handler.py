"""Async HTTP client helpers for outbound service calls."""

from typing import Any, AsyncGenerator
import logging

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class AsyncHttpHandler:
    """
    Thin httpx wrapper for outbound JSON calls.

    Returns parsed JSON on success. Returns None only when the upstream
    responds with 404 (not found). Network failures, malformed responses,
    and other HTTP errors raise HTTPException so callers cannot confuse
    "missing" with "unavailable".
    """

    def __init__(self):
        """Initialize an empty handler (clients are created per request)."""
        pass

    @staticmethod
    def _handle_request_error(
        *,
        method: str,
        url: str,
        exc: BaseException,
        params: dict | None = None,
        json_data: dict | None = None,
        data: dict | None = None,
    ) -> bool:
        """
        Log and classify a failed outbound request.

        Returns:
            True when upstream returned 404 (caller should return None).

        Raises:
            HTTPException: For network failures and non-404 HTTP errors.
        """
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            body = exc.response.text
            if status == 404:
                logger.info(
                    "%s not found url=%s params=%s json_data=%s data=%s",
                    method,
                    url,
                    params,
                    json_data,
                    data,
                )
                return True
            logger.exception(
                "%s failed status=%s url=%s params=%s json_data=%s data=%s "
                "body=%s",
                method,
                status,
                url,
                params,
                json_data,
                data,
                body,
            )
            raise HTTPException(
                status_code=502,
                detail=(f"Upstream returned HTTP {status} for {method} {url}"),
            ) from exc

        if isinstance(exc, httpx.RequestError):
            logger.exception(
                "%s network error url=%s params=%s json_data=%s data=%s "
                "error=%s",
                method,
                url,
                params,
                json_data,
                data,
                exc,
            )
            raise HTTPException(
                status_code=503,
                detail=f"Upstream service unavailable for {method} {url}",
            ) from exc

        logger.exception(
            "%s unexpected error url=%s params=%s json_data=%s data=%s",
            method,
            url,
            params,
            json_data,
            data,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Upstream response error for {method} {url}",
        ) from exc

    async def async_get(
        self, url: str, params: dict = None, headers: dict = None
    ) -> Any | None:
        """
        Perform an async GET and return parsed JSON.

        Args:
            url: Absolute request URL.
            params: Optional query parameters.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the upstream returned 404.

        Raises:
            HTTPException: 503 on network/malformed failures; 502 on other
                upstream HTTP errors.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, params=params, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if self._handle_request_error(
                    method="GET", url=url, exc=e, params=params
                ):
                    return None

    async def async_post(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ) -> Any | None:
        """
        Perform an async POST and return parsed JSON.

        Args:
            url: Absolute request URL.
            data: Optional form body.
            json_data: Optional JSON body.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the upstream returned 404.

        Raises:
            HTTPException: 503 on network/malformed failures; 502 on other
                upstream HTTP errors.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, data=data, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if self._handle_request_error(
                    method="POST",
                    url=url,
                    exc=e,
                    json_data=json_data,
                    data=data,
                ):
                    return None

    async def async_patch(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ) -> Any | None:
        """
        Perform an async PATCH and return parsed JSON.

        Args:
            url: Absolute request URL.
            data: Optional form body.
            json_data: Optional JSON body.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the upstream returned 404.

        Raises:
            HTTPException: 503 on network/malformed failures; 502 on other
                upstream HTTP errors.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    url, data=data, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if self._handle_request_error(
                    method="PATCH",
                    url=url,
                    exc=e,
                    json_data=json_data,
                    data=data,
                ):
                    return None

    async def async_delete(
        self,
        url: str,
        json_data: dict = None,
        headers: dict = None,
    ) -> Any | None:
        """
        Perform an async DELETE and return parsed JSON.

        Args:
            url: Absolute request URL.
            json_data: Optional JSON body.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the upstream returned 404.

        Raises:
            HTTPException: 503 on network/malformed failures; 502 on other
                upstream HTTP errors.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    "DELETE", url, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if self._handle_request_error(
                    method="DELETE", url=url, exc=e, json_data=json_data
                ):
                    return None


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """FastAPI dependency that yields the shared AsyncHttpHandler."""
    yield handler
