import logging
from typing import AsyncGenerator

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_UNAVAILABLE = "Downstream service unavailable"


def _response_detail(e: httpx.HTTPStatusError) -> str:
    try:
        return e.response.json().get("detail", e.response.text)
    except Exception:
        return e.response.text


def _raise_for_status(e: httpx.HTTPStatusError) -> None:
    """Re-raise a downstream HTTP failure.

    A 5xx becomes 503 so an outage is not mistaken for a missing record.
    Every other status, including 3xx and 4xx, keeps its own code.
    """
    status_code = e.response.status_code
    if status_code >= 500:
        logger.warning("Downstream %s from %s", status_code, e.request.url)
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    raise HTTPException(status_code=status_code, detail=_response_detail(e))


def _raise_if_unavailable(e: httpx.RequestError) -> None:
    """A connection failure or timeout is a 503, not a missing record."""
    logger.warning("Downstream request failed: %s", e)
    raise HTTPException(status_code=503, detail=_UNAVAILABLE)


class AsyncHttpHandler:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    def set_client(self, client: httpx.AsyncClient) -> None:
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "httpx.AsyncClient not initialised — "
                "ensure the app lifespan has started"
            )
        return self._client

    async def async_get(
        self, url: str, params: dict = None, headers: dict = None
    ):
        client = self._get_client()
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            _raise_for_status(e)
        except httpx.RequestError as e:
            _raise_if_unavailable(e)

    async def async_post(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        client = self._get_client()
        try:
            response = await client.post(
                url, data=data, json=json_data, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            _raise_for_status(e)
        except httpx.RequestError as e:
            _raise_if_unavailable(e)

    async def async_patch(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        client = self._get_client()
        try:
            response = await client.patch(
                url, data=data, json=json_data, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            _raise_for_status(e)
        except httpx.RequestError as e:
            _raise_if_unavailable(e)

    async def async_put(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        client = self._get_client()
        try:
            response = await client.put(
                url, data=data, json=json_data, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            _raise_for_status(e)
        except httpx.RequestError as e:
            _raise_if_unavailable(e)

    async def async_delete(
        self,
        url: str,
        json_data: dict = None,
        headers: dict = None,
    ):
        client = self._get_client()
        try:
            response = await client.request(
                "DELETE", url, json=json_data, headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            _raise_for_status(e)
        except httpx.RequestError as e:
            _raise_if_unavailable(e)


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """
    Yields a globally shared AsyncHttpHandler instance.

    Reuses the same instance for all requests, given the stateless nature of
    the handler.
    """
    yield handler
