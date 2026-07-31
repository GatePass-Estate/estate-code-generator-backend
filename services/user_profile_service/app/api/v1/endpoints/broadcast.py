from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.broadcast import BroadcastRepository
from app.repositories.estate import EstateRepository
from app.repositories.user import UserRepository
from app.schemas.broadcast import (
    BroadcastCreateResponse,
    BroadcastDeleteResponse,
    BroadcastItem,
    BroadcastListResponse,
    BroadcastReadResponse,
    BroadcastUpdateResponse,
    CreateBroadcastRequest,
    DismissAllResponse,
    UnreadBroadcastCountResponse,
    UpdateBroadcastRequest,
)
from app.services.auth import get_current_user
from app.services.broadcast import BroadcastService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> BroadcastService:
    return BroadcastService(
        broadcast_repo=BroadcastRepository(ahttp_client),
        estate_repo=EstateRepository(ahttp_client),
        user_repo=UserRepository(ahttp_client),
        http_client=ahttp_client,
    )


@router.post("", status_code=201, response_model=BroadcastCreateResponse)
async def create_broadcast(
    request: CreateBroadcastRequest,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Create and deliver a broadcast. Requires can_create_broadcast."""
    try:
        return await service.create_and_deliver(
            request,
            requester_id=str(current_user["id"]),
            requester_role=current_user["role"],
            requester_estate_id=(
                str(current_user["estate_id"])
                if current_user.get("estate_id")
                else None
            ),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error creating broadcast")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unread-count", response_model=UnreadBroadcastCountResponse)
async def unread_count(
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
) -> UnreadBroadcastCountResponse:
    """Count broadcasts visible to the current user that they haven't read."""
    estate_id = str(current_user.get("estate_id") or "")
    roles = [current_user["role"]]
    return await service.unread_count(
        user_id=str(current_user["id"]),
        estate_id=estate_id,
        roles=roles,
    )


@router.get("", response_model=BroadcastListResponse)
async def list_broadcasts(
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
) -> BroadcastListResponse:
    """List broadcasts visible to the current user."""
    estate_id = str(current_user.get("estate_id") or "")
    roles = [current_user["role"]]
    return await service.list_for_user(
        user_id=str(current_user["id"]),
        estate_id=estate_id,
        roles=roles,
        page=page,
        limit=limit,
    )


@router.get("/{broadcast_id}", response_model=BroadcastItem)
async def get_broadcast(
    broadcast_id: str,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Get a single broadcast by ID (scoped to user's estate and role)."""
    try:
        return await service.get(
            broadcast_id,
            requester_estate_id=str(current_user.get("estate_id") or ""),
            requester_role=current_user["role"],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error fetching broadcast")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{broadcast_id}/read",
    status_code=200,
    response_model=BroadcastReadResponse,
)
async def mark_broadcast_read(
    broadcast_id: str,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Mark a broadcast as read for the current user."""
    return await service.mark_read(
        broadcast_id=broadcast_id,
        user_id=str(current_user["id"]),
        requester_estate_id=str(current_user.get("estate_id") or ""),
        requester_role=current_user["role"],
    )


@router.post(
    "/{broadcast_id}/dismiss",
    status_code=200,
    response_model=BroadcastReadResponse,
)
async def dismiss_broadcast(
    broadcast_id: str,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Dismiss a BROADCAST-category broadcast for the current user."""
    try:
        return await service.dismiss(
            broadcast_id=broadcast_id,
            user_id=str(current_user["id"]),
            requester_estate_id=str(current_user.get("estate_id") or ""),
            requester_role=current_user["role"],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error dismissing broadcast")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/dismiss-all", status_code=200, response_model=DismissAllResponse
)
async def dismiss_all_broadcasts(
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Dismiss all BROADCAST-category broadcasts for the current user."""
    estate_id = str(current_user.get("estate_id") or "")
    try:
        return await service.dismiss_all(
            user_id=str(current_user["id"]), estate_id=estate_id
        )
    except Exception:
        logger.exception("Unexpected error dismissing all broadcasts")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{broadcast_id}", response_model=BroadcastUpdateResponse)
async def update_broadcast(
    broadcast_id: str,
    payload: UpdateBroadcastRequest,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Update a broadcast (sender or root only)."""
    try:
        return await service.update(
            broadcast_id,
            payload,
            requester_id=str(current_user["id"]),
            requester_role=current_user["role"],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error updating broadcast")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{broadcast_id}",
    status_code=200,
    response_model=BroadcastDeleteResponse,
)
async def delete_broadcast(
    broadcast_id: str,
    current_user: dict = Depends(get_current_user),
    service: BroadcastService = Depends(_get_service),
):
    """Delete a broadcast (sender or root only)."""
    try:
        return await service.delete(
            broadcast_id,
            requester_id=str(current_user["id"]),
            requester_role=current_user["role"],
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error deleting broadcast")
        raise HTTPException(status_code=500, detail="Internal server error")
