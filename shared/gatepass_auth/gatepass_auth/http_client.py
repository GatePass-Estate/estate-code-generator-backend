from typing import Optional

import httpx


async def async_get(url: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def async_patch(url: str, data: dict) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.patch(url, json=data)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
