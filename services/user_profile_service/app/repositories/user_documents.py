"""HTTP client for db-service user document endpoints."""

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
    """Open streaming response from db-service plus its HTTP client."""

    response: httpx.Response
    client: httpx.AsyncClient

    async def close(self) -> None:
        """Close the streaming response and underlying HTTP client."""
        await self.response.aclose()
        await self.client.aclose()


class UserDocumentsRepository:
    """HTTP client to db-service user document endpoints."""

    def __init__(self, http_client: AsyncHttpHandler) -> None:
        """Configure the db-service user documents base URL."""
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
        uploader_role: str,
    ) -> dict[str, Any]:
        """Multipart upload to db-service and return the JSON response."""
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
            "uploader_role": uploader_role,
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

    async def get_active_by_user_and_type(
        self, user_id: str, document_type: str
    ) -> dict[str, Any] | None:
        """Fetch the active document metadata row for a user and type."""
        params = urlencode(
            {
                "user_id": user_id,
                "document_type": document_type,
                "document_status": "active",
                "page": 1,
                "limit": 1,
            }
        )
        url = f"{self.endpoint}/search?{params}"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch user document metadata",
            )
        items = response.get("items", [])
        return items[0] if items else None

    async def search_by_user(
        self,
        user_id: str,
        *,
        document_type: str | None = None,
        document_status: list[str] | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Search document metadata rows for a user via db-service.

        ``document_status`` may contain multiple values; each is sent as a
        repeated query parameter.
        """
        query_pairs: list[tuple[str, str | int]] = [
            ("user_id", user_id),
            ("page", page),
            ("limit", limit),
        ]
        if document_type is not None:
            query_pairs.append(("document_type", document_type))
        if document_status:
            for status in document_status:
                query_pairs.append(("document_status", status))
        params = urlencode(query_pairs)
        url = f"{self.endpoint}/search?{params}"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch user documents metadata",
            )
        return response

    async def get_by_id(self, document_id: str) -> dict[str, Any]:
        """Fetch a document metadata row by ID."""
        url = f"{self.endpoint}/{document_id}"
        response = await self.client.async_get(url)
        if response is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )
        return response

    async def approve(self, document_id: str) -> dict[str, Any]:
        """Promote a pending document to active via db-service."""
        url = f"{self.endpoint}/{document_id}/approve"
        async with httpx.AsyncClient(
            timeout=_STREAM_TIMEOUT_SECONDS
        ) as http_client:
            try:
                response = await http_client.post(url)
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
                logger.exception("Approve request failed")
                raise HTTPException(
                    status_code=503,
                    detail="Document service unavailable",
                ) from e

    async def stream_from_db_service(
        self, user_id: str, document_type: str
    ) -> DocumentStream:
        """Open a streaming GET to db-service for document bytes."""
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
        """Delete all documents for a user via db-service."""
        url = f"{self.endpoint}/user/{user_id}"
        response = await self.client.async_delete(url)
        return response
