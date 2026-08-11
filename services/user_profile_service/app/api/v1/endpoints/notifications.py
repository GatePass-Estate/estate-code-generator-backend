from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from gatepass_auth import get_current_user

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.notification import NotificationRepository
from app.schemas.notification import (
    DeleteAllNotificationsResponse,
    DeleteNotificationResponse,
    ListNotificationsResponse,
    MarkReadResponse,
    UnreadCountResponse,
)

router = APIRouter()


@router.get("", response_model=ListNotificationsResponse)
async def list_notifications(
    is_read: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationRepository(ahttp_client)
    result = await repo.list_for_user(
        user_id=current_user["id"],
        is_read=is_read,
        max_age_days=settings.NOTIFICATION_MAX_AGE_DAYS,
        page=page,
        limit=limit,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch notifications",
        )
    return result


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationRepository(ahttp_client)
    result = await repo.unread_count(
        user_id=current_user["id"],
        max_age_days=settings.NOTIFICATION_MAX_AGE_DAYS,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch unread count",
        )
    return result


@router.patch("/read-all", response_model=dict)
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationRepository(ahttp_client)
    result = await repo.mark_all_read(user_id=current_user["id"])
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to mark all notifications as read",
        )
    return result


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationRepository(ahttp_client)
    result = await repo.mark_read(
        notification_id=notification_id,
        user_id=current_user["id"],
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to mark notification as read",
        )
    return result


@router.delete("/{notification_id}", response_model=DeleteNotificationResponse)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationRepository(ahttp_client)
    result = await repo.delete_by_id(
        notification_id=notification_id,
        user_id=current_user["id"],
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to delete notification",
        )
    return result


@router.delete("", response_model=DeleteAllNotificationsResponse)
async def delete_all_notifications(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationRepository(ahttp_client)
    result = await repo.delete_all(user_id=current_user["id"])
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to delete notifications",
        )
    return result
