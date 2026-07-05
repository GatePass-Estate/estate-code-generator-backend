"""Tests for internal GCS signed URL cache."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.libs import signed_url_cache


def test_get_or_sign_cache_miss_generates_url():
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed.example/a"
    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    url = signed_url_cache.get_or_sign(
        "user-1",
        "profile_picture",
        "estates/e1/users/user-1/profile_picture.jpg",
        client=mock_client,
    )

    assert url == "https://signed.example/a"
    mock_blob.generate_signed_url.assert_called_once_with(
        version="v4",
        expiration=signed_url_cache.settings.GCS_SIGNED_URL_EXPIRY_SECONDS,
        method="GET",
    )


def test_get_or_sign_cache_hit_skips_signing():
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed.example/a"
    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    path = "estates/e1/users/user-1/profile_picture.jpg"
    first = signed_url_cache.get_or_sign(
        "user-1", "profile_picture", path, client=mock_client
    )
    second = signed_url_cache.get_or_sign(
        "user-1", "profile_picture", path, client=mock_client
    )

    assert first == second == "https://signed.example/a"
    mock_blob.generate_signed_url.assert_called_once()


def test_invalidate_single_document_type():
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.side_effect = [
        "https://signed.example/picture",
        "https://signed.example/id",
        "https://signed.example/picture-v2",
    ]
    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    signed_url_cache.get_or_sign(
        "user-1",
        "profile_picture",
        "estates/e1/users/user-1/profile_picture.jpg",
        client=mock_client,
    )
    signed_url_cache.get_or_sign(
        "user-1",
        "id_card",
        "estates/e1/users/user-1/id_card.pdf",
        client=mock_client,
    )

    signed_url_cache.invalidate("user-1", "profile_picture")

    signed_url_cache.get_or_sign(
        "user-1",
        "profile_picture",
        "estates/e1/users/user-1/profile_picture.jpg",
        client=mock_client,
    )
    signed_url_cache.get_or_sign(
        "user-1",
        "id_card",
        "estates/e1/users/user-1/id_card.pdf",
        client=mock_client,
    )

    assert mock_blob.generate_signed_url.call_count == 3


def test_invalidate_all_for_user():
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.side_effect = [
        "https://signed.example/u1",
        "https://signed.example/u2",
        "https://signed.example/u1-new",
    ]
    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    signed_url_cache.get_or_sign(
        "user-1",
        "profile_picture",
        "estates/e1/users/user-1/profile_picture.jpg",
        client=mock_client,
    )
    signed_url_cache.get_or_sign(
        "user-2",
        "profile_picture",
        "estates/e1/users/user-2/profile_picture.jpg",
        client=mock_client,
    )

    signed_url_cache.invalidate("user-1")

    signed_url_cache.get_or_sign(
        "user-1",
        "profile_picture",
        "estates/e1/users/user-1/profile_picture.jpg",
        client=mock_client,
    )
    signed_url_cache.get_or_sign(
        "user-2",
        "profile_picture",
        "estates/e1/users/user-2/profile_picture.jpg",
        client=mock_client,
    )

    assert mock_blob.generate_signed_url.call_count == 3
