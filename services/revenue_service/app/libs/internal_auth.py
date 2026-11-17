"""Dependency for cluster-internal endpoints protected by a shared API key."""

from typing import Annotated

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_internal_key(
    x_internal_key: Annotated[str, Header(alias="X-Internal-Key")],
) -> None:
    """
    Validate the ``X-Internal-Key`` header against ``INTERNAL_API_KEY``.

    Raises:
        HTTPException: 403 if the key is missing or incorrect;
            500 if ``INTERNAL_API_KEY`` is not configured.
    """
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="INTERNAL_API_KEY is not configured on this server",
        )
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal API key")
