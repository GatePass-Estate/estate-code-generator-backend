from typing import AsyncGenerator

import httpx


class AsyncHttpHandler:
    def __init__(self):
        pass

    async def async_get(
        self, url: str, params: dict = None, headers: dict = None
    ):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, params=params, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
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
        params: dict = None,
        headers: dict = None,
    ):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    data=data,
                    json=json_data,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(
                    f"POST request failed with status {e.response.status_code}"
                    f": {e.response.text}"
                )
            except httpx.RequestError as e:
                print(f"POST request encountered a network error: {e}")
            except Exception as e:
                print(f"POST request unexpected error: {e}")
        return None

    async def async_put(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        headers: dict = None,
    ):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    url, data=data, json=json_data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(
                    f"PUT request failed with status {e.response.status_code}"
                    f": {e.response.text}"
                )
            except httpx.RequestError as e:
                print(f"PUT request encountered a network error: {e}")
            except Exception as e:
                print(f"PUT request unexpected error: {e}")
        return None

    async def async_patch(
        self,
        url: str,
        data: dict = None,
        json_data: dict = None,
        params: dict = None,
        headers: dict = None,
    ):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    url,
                    data=data,
                    json=json_data,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
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

    async def async_delete(
        self,
        url: str,
        params: dict = None,
        headers: dict = None,
    ):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    url, params=params, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
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
    yield handler
