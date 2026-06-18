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
    def __init__(self):
        pass

    async def async_get(
        self, url: str, params: dict = None, headers: dict = None
    ):
        """
        Performs an asynchronous GET request using httpx.

        :param url: URL to request.
        :param params: (Optional) Dictionary of URL parameters.
        :param headers: (Optional) Dictionary of HTTP headers.
        :return: Parsed JSON response, or None if an error occurred.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, params=params, headers=headers
                )
                # This will raise an error if the response status is 4xx or 5xx
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
                raise Exception(
                    f"GET request encountered a network error: {e}"
                )
            except Exception as e:
                raise Exception(f"GET request unexpected error: {e}")
        return None

    async def async_post(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        """
        Performs an asynchronous POST request using httpx.

        :param url: URL to request.
        :param data: (Optional) Dictionary of form data.
        :param json_data: (Optional) Dictionary of JSON payload.
        :param headers: (Optional) Dictionary of HTTP headers.
        :return: Parsed JSON response, or None if an error occurred.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, data=data, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                _raise_post_http_error(e)
            except httpx.RequestError as e:
                raise Exception(
                    f"POST request encountered a network error: {e}"
                )
            except Exception as e:
                raise Exception(f"POST request unexpected error: {e}")
        return None

    async def async_delete(
        self,
        url: str,
        headers: dict = None,
    ):
        """
        Performs an asynchronous DELETE request using httpx.

        :param url: URL to request.
        :param headers: (Optional) Dictionary of HTTP headers.
        :return: Parsed JSON response, or None if an error occurred.
        """
        async with httpx.AsyncClient() as client:
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
                raise Exception(
                    f"DELETE request encountered a network error: {e}"
                )
            except Exception as e:
                raise Exception(f"DELETE request unexpected error: {e}")

    async def async_patch(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        """
        Performs an asynchronous PATCH request using httpx.

        :param url: URL to request.
        :param data: (Optional) Dictionary of form data.
        :param json_data: (Optional) Dictionary of JSON payload.
        :param headers: (Optional) Dictionary of HTTP headers.
        :return: Parsed JSON response, or None if an error occurred.
        """
        async with httpx.AsyncClient() as client:
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
                raise Exception(
                    f"PATCH request encountered a network error: {e}"
                )
            except Exception as e:
                raise Exception(f"PATCH request unexpected error: {e}")
        return None


handler = AsyncHttpHandler()


async def get_http_handler() -> AsyncGenerator[AsyncHttpHandler, None]:
    """
    Yields a globally shared AsyncHttpHandler instance.

    Reuses the same instance for all requests, given the stateless nature of
    the handler.
    """
    yield handler
