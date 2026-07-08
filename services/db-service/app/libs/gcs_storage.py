"""GCS object upload, delete, and stream helpers for user documents."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import BinaryIO

import httpx
from google.cloud import storage

from app.core.config import settings

_STREAM_CHUNK_SIZE = 64 * 1024
_STREAM_TIMEOUT_SECONDS = 60.0


def _get_client(client: storage.Client | None = None) -> storage.Client:
    return client or storage.Client()


def _get_blob(
    object_path: str,
    *,
    client: storage.Client | None = None,
):
    gcs_client = _get_client(client)
    return gcs_client.bucket(settings.GCS_DOCUMENTS_BUCKET).blob(object_path)


async def upload_object(
    object_path: str,
    file_obj: BinaryIO,
    content_type: str,
    *,
    client: storage.Client | None = None,
) -> None:
    """Upload a file object to GCS at the given path."""

    def _upload() -> None:
        blob = _get_blob(object_path, client=client)
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        blob.upload_from_file(file_obj, content_type=content_type)

    await asyncio.to_thread(_upload)


async def copy_object(
    source_path: str,
    destination_path: str,
    *,
    client: storage.Client | None = None,
) -> None:
    """Copy a GCS object to a new path within the same bucket."""

    def _copy() -> None:
        gcs_client = _get_client(client)
        bucket = gcs_client.bucket(settings.GCS_DOCUMENTS_BUCKET)
        bucket.copy_blob(
            bucket.blob(source_path),
            bucket,
            destination_path,
        )

    await asyncio.to_thread(_copy)


async def move_object(
    source_path: str,
    destination_path: str,
    *,
    client: storage.Client | None = None,
) -> None:
    """
    Copy a GCS object to a new path and delete the source.

    Requires ``storage.objects.create`` and ``storage.objects.delete`` on the
    bucket for the service account.
    """
    await copy_object(source_path, destination_path, client=client)
    await delete_object(source_path, client=client)


async def delete_object(
    object_path: str,
    *,
    client: storage.Client | None = None,
) -> None:
    """Delete a GCS object by path."""

    def _delete() -> None:
        _get_blob(object_path, client=client).delete()

    await asyncio.to_thread(_delete)


async def stream_object(signed_url: str) -> AsyncIterator[bytes]:
    """Stream object bytes from GCS via an internal signed URL."""
    async with httpx.AsyncClient(
        timeout=_STREAM_TIMEOUT_SECONDS
    ) as http_client:
        async with http_client.stream("GET", signed_url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(
                chunk_size=_STREAM_CHUNK_SIZE
            ):
                yield chunk
