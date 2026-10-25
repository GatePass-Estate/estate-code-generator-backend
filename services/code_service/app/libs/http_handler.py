from typing import AsyncGenerator

import httpx

from app.core.exceptions import NotFoundError, ScheduleError


def _extract_error_detail(response: httpx.Response) -> str | dict:
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text


def _raise_post_http_error(error: httpx.HTTPStatusError) -> None:
    if error.response.status_code == 400:
        detail = _extract_error_detail(error.response)
        if (
            isinstance(detail, dict)
            and detail.get("code") == ScheduleError.code
        ):
            raise ScheduleError(detail.get("message", str(detail))) from error
    raise Exception(
        f"POST request failed with status {error.response.status_code}"
        f": {error.response.text}"
    ) from error


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
            if e.response.status_code == 404:
                raise NotFoundError(
                    f"GET request failed with status "
                    f" {e.response.status_code}: {e.response.text}"
                )
            raise Exception(
                f"GET request failed with status {e.response.status_code}:"
                f" {e.response.text}"
            )
        except httpx.RequestError as e:
            raise Exception(f"GET request encountered a network error: {e}")

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
            _raise_post_http_error(e)
        except httpx.RequestError as e:
            raise Exception(f"POST request encountered a network error: {e}")

    async def async_delete(
        self,
        url: str,
        headers: dict = None,
    ):
        client = self._get_client()
        try:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(
                f"DELETE req. failed with status {e.response.status_code}"
                f": {e.response.text}"
            )
        except httpx.RequestError as e:
            raise Exception(f"DELETE request encountered a network error: {e}")

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
            raise Exception(
                "PATCH request failed with status "
                f"{e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise Exception(f"PATCH request encountered a network error: {e}")


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """
    Yields a globally shared AsyncHttpHandler instance.

    Reuses the same instance for all requests, given the stateless nature of
    the handler.
    """
    yield handler
