import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler

logger = logging.getLogger(__name__)

_STREAM_TIMEOUT_SECONDS = 60.0


@dataclass
class DocumentStream:
    response: httpx.Response
    client: httpx.AsyncClient

    async def close(self) -> None:
        await self.response.aclose()
        await self.client.aclose()


class UserDocumentsRepository:
    """HTTP client to db-service user document endpoints."""

    def __init__(self, http_client: AsyncHttpHandler) -> None:
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.endpoint = f"{self.base_url}api/v1/userprofile/userdocuments"

    async def upload(
        self,
        *,
        file_bytes: bytes,
        filename: str | None,
        content_type: str,
        user_id: str,
        estate_id: str,
        document_type: str,
    ) -> dict[str, Any]:
        files = {
            "file": (
                filename or "upload",
                file_bytes,
                content_type,
            )
        }
        data = {
            "user_id": user_id,
            "estate_id": estate_id,
            "document_type": document_type,
        }
        async with httpx.AsyncClient(
            timeout=_STREAM_TIMEOUT_SECONDS
        ) as http_client:
            try:
                response = await http_client.post(
                    f"{self.endpoint}/upload",
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                detail = e.response.text
                try:
                    detail = e.response.json().get("detail", detail)
                except ValueError:
                    pass
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=detail,
                ) from e
            except httpx.RequestError as e:
                logger.exception("Upload request failed")
                raise HTTPException(
                    status_code=503,
                    detail="Document service unavailable",
                ) from e

    async def search_by_user(
        self, user_id: str, page: int = 1, limit: int = 20
    ) -> dict[str, Any]:
        params = urlencode({"user_id": user_id, "page": page, "limit": limit})
        url = f"{self.endpoint}/search?{params}"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch user documents metadata",
            )
        return response

    async def stream_from_db_service(
        self, user_id: str, document_type: str
    ) -> DocumentStream:
        url = f"{self.endpoint}/{user_id}/{document_type}/stream"
        http_client = httpx.AsyncClient(timeout=_STREAM_TIMEOUT_SECONDS)
        try:
            response = await http_client.send(
                http_client.build_request("GET", url),
                stream=True,
            )
            response.raise_for_status()
            return DocumentStream(response=response, client=http_client)
        except httpx.HTTPStatusError as e:
            await http_client.aclose()
            detail = e.response.text
            try:
                detail = e.response.json().get("detail", detail)
            except ValueError:
                pass
            raise HTTPException(
                status_code=e.response.status_code,
                detail=detail,
            ) from e
        except httpx.RequestError as e:
            await http_client.aclose()
            logger.exception("Stream request failed")
            raise HTTPException(
                status_code=503,
                detail="Document service unavailable",
            ) from e

    async def delete_all_for_user(self, user_id: str) -> dict[str, Any] | None:
        url = f"{self.endpoint}/user/{user_id}"
        response = await self.client.async_delete(url)
        return response
