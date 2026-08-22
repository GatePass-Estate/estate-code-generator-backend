"""Async HTTP client helpers for outbound service calls."""

from typing import AsyncGenerator
import logging

import httpx

logger = logging.getLogger(__name__)


class AsyncHttpHandler:
    """Thin httpx wrapper that returns JSON or None on failure."""

    def __init__(self):
        """Initialize an empty handler (clients are created per request)."""
        pass

    async def async_get(
        self, url: str, params: dict = None, headers: dict = None
    ):
        """
        Perform an async GET and return parsed JSON.

        Args:
            url: Absolute request URL.
            params: Optional query parameters.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the request failed.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, params=params, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.exception(
                    "GET failed status=%s url=%s params=%s body=%s",
                    e.response.status_code,
                    url,
                    params,
                    e.response.text,
                )
            except httpx.RequestError as e:
                logger.exception(
                    "GET network error url=%s params=%s error=%s",
                    url,
                    params,
                    e,
                )
            except Exception:
                logger.exception(
                    "GET unexpected error url=%s params=%s",
                    url,
                    params,
                )
        return None

    async def async_post(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        """
        Perform an async POST and return parsed JSON.

        Args:
            url: Absolute request URL.
            data: Optional form body.
            json_data: Optional JSON body.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the request failed.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, data=data, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.exception(
                    "POST failed status=%s url=%s json_data=%s data=%s body=%s",
                    e.response.status_code,
                    url,
                    json_data,
                    data,
                    e.response.text,
                )
            except httpx.RequestError as e:
                logger.exception(
                    "POST network error url=%s json_data=%s data=%s error=%s",
                    url,
                    json_data,
                    data,
                    e,
                )
            except Exception:
                logger.exception(
                    "POST unexpected error url=%s json_data=%s data=%s",
                    url,
                    json_data,
                    data,
                )
        return None

    async def async_patch(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        """
        Perform an async PATCH and return parsed JSON.

        Args:
            url: Absolute request URL.
            data: Optional form body.
            json_data: Optional JSON body.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the request failed.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    url, data=data, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.exception(
                    "PATCH failed status=%s url=%s json_data=%s data=%s body=%s",
                    e.response.status_code,
                    url,
                    json_data,
                    data,
                    e.response.text,
                )
            except httpx.RequestError as e:
                logger.exception(
                    "PATCH network error url=%s json_data=%s data=%s error=%s",
                    url,
                    json_data,
                    data,
                    e,
                )
            except Exception:
                logger.exception(
                    "PATCH unexpected error url=%s json_data=%s data=%s",
                    url,
                    json_data,
                    data,
                )
        return None

    async def async_delete(
        self,
        url: str,
        json_data: dict = None,
        headers: dict = None,
    ):
        """
        Perform an async DELETE and return parsed JSON.

        Args:
            url: Absolute request URL.
            json_data: Optional JSON body.
            headers: Optional HTTP headers.

        Returns:
            Parsed JSON body, or None if the request failed.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    "DELETE", url, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.exception(
                    "DELETE failed status=%s url=%s json_data=%s body=%s",
                    e.response.status_code,
                    url,
                    json_data,
                    e.response.text,
                )
            except httpx.RequestError as e:
                logger.exception(
                    "DELETE network error url=%s json_data=%s error=%s",
                    url,
                    json_data,
                    e,
                )
            except Exception:
                logger.exception(
                    "DELETE unexpected error url=%s json_data=%s",
                    url,
                    json_data,
                )
        return None


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """FastAPI dependency that yields the shared AsyncHttpHandler."""
    yield handler
