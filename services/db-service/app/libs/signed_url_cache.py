"""In-process TTL cache for internal GCS signed URLs (db-service only)."""

from __future__ import annotations

from cachetools import TTLCache
from google.cloud import storage

from app.core.config import settings

_cache: TTLCache = TTLCache(
    maxsize=10_000,
    ttl=settings.GCS_SIGNED_URL_EXPIRY_SECONDS,
)


def _sign_gcs_url(
    object_path: str,
    *,
    client: storage.Client | None = None,
) -> str:
    gcs_client = client or storage.Client()
    blob = gcs_client.bucket(settings.GCS_DOCUMENTS_BUCKET).blob(object_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=settings.GCS_SIGNED_URL_EXPIRY_SECONDS,
        method="GET",
    )


def get_or_sign(
    target_user_id: str,
    document_type: str,
    object_path: str,
    *,
    client: storage.Client | None = None,
) -> str:
    """Return a cached signed URL or generate and cache a new one."""
    key = (target_user_id, document_type)
    signed = _cache.get(key)
    if signed:
        return signed
    signed = _sign_gcs_url(object_path, client=client)
    _cache[key] = signed
    return signed


def invalidate(
    target_user_id: str,
    document_type: str | None = None,
) -> None:
    """Drop cached signed URLs after upload or account closure."""
    if document_type:
        _cache.pop((target_user_id, document_type), None)
        return
    for key in list(_cache.keys()):
        if key[0] == target_user_id:
            del _cache[key]


def clear_cache() -> None:
    """Clear all cached signed URLs (for tests)."""
    _cache.clear()
