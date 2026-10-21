from typing import AsyncGenerator

import httpx
from fastapi import HTTPException


def _raise_if_client_error(e: httpx.HTTPStatusError) -> None:
    """Re-raise 4xx responses from downstream services as HTTPException."""
    if 400 <= e.response.status_code < 500:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except Exception:
            detail = e.response.text
        raise HTTPException(status_code=e.response.status_code, detail=detail)


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
            _raise_if_client_error(e)
            print(
                f"GET request failed with status {e.response.status_code}:"
                f" {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"GET request encountered a network error: {e}")
        except Exception as e:
            print(f"GET request unexpected error: {e}")
        return None

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
            _raise_if_client_error(e)
            print(
                f"POST request failed with status {e.response.status_code}"
                f": {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"POST request encountered a network error: {e}")
        except Exception as e:
            print(f"POST request unexpected error: {e}")
        return None

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
            _raise_if_client_error(e)
            print(
                f"PATCH request failed"
                f" with status {e.response.status_code}"
                f": {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"PATCH request encountered a network error: {e}")
        except Exception as e:
            print(f"PATCH request unexpected error: {e}")
        return None

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
            _raise_if_client_error(e)
            print(
                f"PUT request failed"
                f" with status {e.response.status_code}"
                f": {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"PUT request encountered a network error: {e}")
        except Exception as e:
            print(f"PUT request unexpected error: {e}")
        return None

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
            _raise_if_client_error(e)
            print(
                f"DELETE request failed"
                f" with status {e.response.status_code}"
                f": {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"DELETE request encountered a network error: {e}")
        except Exception as e:
            print(f"DELETE request unexpected error: {e}")
        return None


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """
    Yields a globally shared AsyncHttpHandler instance.

    Reuses the same instance for all requests, given the stateless nature of
    the handler.
    """
    yield handler
