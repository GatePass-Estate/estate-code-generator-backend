"""Tests for GCS storage helpers."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.libs import gcs_storage


@pytest.mark.asyncio
async def test_upload_object_uploads_to_bucket():
    file_obj = BytesIO(b"jpeg-bytes")
    mock_blob = MagicMock()
    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    await gcs_storage.upload_object(
        "estates/e1/users/u1/profile_picture.jpg",
        file_obj,
        "image/jpeg",
        client=mock_client,
    )

    mock_client.bucket.assert_called_once_with(
        gcs_storage.settings.GCS_DOCUMENTS_BUCKET
    )
    mock_client.bucket.return_value.blob.assert_called_once_with(
        "estates/e1/users/u1/profile_picture.jpg"
    )
    mock_blob.upload_from_file.assert_called_once_with(
        file_obj, content_type="image/jpeg"
    )


@pytest.mark.asyncio
async def test_delete_object_deletes_blob():
    mock_blob = MagicMock()
    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    await gcs_storage.delete_object(
        "estates/e1/users/u1/id_card.pdf",
        client=mock_client,
    )

    mock_blob.delete.assert_called_once_with()


@pytest.mark.asyncio
async def test_stream_object_yields_chunks():
    chunks = [b"part-a", b"part-b"]

    class FakeStreamResponse:
        def __init__(self, parts):
            self._parts = parts

        def raise_for_status(self):
            return None

        async def aiter_bytes(self, chunk_size=65536):
            for part in self._parts:
                yield part

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url):
            assert method == "GET"
            assert url == "https://signed.example/object"
            return FakeStreamResponse(chunks)

    with patch(
        "app.libs.gcs_storage.httpx.AsyncClient",
        return_value=FakeClient(),
    ):
        received = [
            chunk
            async for chunk in gcs_storage.stream_object(
                "https://signed.example/object"
            )
        ]

    assert received == chunks
