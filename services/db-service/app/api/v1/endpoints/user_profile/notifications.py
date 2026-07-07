import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError
from app.db.session import get_db_session
from app.schemas.user_profile.notifications import (
    CreateNotificationRequest,
    CreateNotificationResponse,
    DeleteAllNotificationsResponse,
    DeleteNotificationResponse,
    ListDeviceTokensResponse,
    ListNotificationsResponse,
    ListPreferencesResponse,
    MarkReadResponse,
    GetPreferenceResponse,
    RegisterDeviceTokenRequest,
    RegisterDeviceTokenResponse,
    UnreadCountResponse,
    UpsertPreferenceRequest,
)
from app.services.user_profile.notifications import (
    NotificationsService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    return Service(db_session=db_session)


@router.post(
    "",
    response_model=CreateNotificationResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a single notification row",
)
async def create_notification(
    request: CreateNotificationRequest,
    service: Service = Depends(get_service),
) -> CreateNotificationResponse:
    try:
        return await service.create_notification(request=request)
    except DatabaseError as e:
        logger.exception(
            "Database error creating notification for user_id=%s type=%s",
            request.user_id,
            request.type,
        )
        raise HTTPException(
            status_code=500, detail="Failed to create notification"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error creating notification for user_id=%s type=%s",
            request.user_id,
            request.type,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/bulk",
    response_model=List[CreateNotificationResponse],
    status_code=status.HTTP_201_CREATED,
    description="Create multiple notification rows (fan-out)",
)
async def create_notifications_bulk(
    requests: List[CreateNotificationRequest],
    service: Service = Depends(get_service),
) -> List[CreateNotificationResponse]:
    try:
        return await service.create_notifications_bulk(requests=requests)
    except DatabaseError as e:
        logger.exception(
            "Database error bulk-creating %d notifications", len(requests)
        )
        raise HTTPException(
            status_code=500, detail="Failed to bulk-create notifications"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error bulk-creating %d notifications", len(requests)
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "",
    response_model=ListNotificationsResponse,
    status_code=status.HTTP_200_OK,
    description="List notifications for a user",
)
async def list_notifications(
    user_id: UUID4,
    is_read: bool | None = None,
    max_age_days: int = 90,
    page: int = 1,
    limit: int = 20,
    service: Service = Depends(get_service),
) -> ListNotificationsResponse:
    try:
        return await service.list_notifications(
            user_id=user_id,
            is_read=is_read,
            max_age_days=max_age_days,
            page=page,
            limit=limit,
        )
    except DatabaseError as e:
        logger.exception(
            "Database error listing notifications for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to list notifications"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error listing notifications for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    description="Count unread notifications for a user",
)
async def unread_count(
    user_id: UUID4,
    max_age_days: int = 90,
    service: Service = Depends(get_service),
) -> UnreadCountResponse:
    try:
        return await service.unread_count(
            user_id=user_id, max_age_days=max_age_days
        )
    except DatabaseError as e:
        logger.exception(
            "Database error counting unread notifications for user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to count unread notifications"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error counting unread notifications for user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch(
    "/{notification_id}/read",
    response_model=MarkReadResponse,
    status_code=status.HTTP_200_OK,
    description="Mark a single notification as read",
)
async def mark_read(
    notification_id: UUID4,
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> MarkReadResponse:
    try:
        return await service.mark_read(
            notification_id=notification_id, user_id=user_id
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Notification {notification_id} "
            f"not found for user {user_id}",
        ) from e
    except DatabaseError as e:
        logger.exception(
            "Database error marking notification_id=%s read for user_id=%s",
            notification_id,
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to mark notification as read"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error marking notification_id=%s read for user_id=%s",
            notification_id,
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch(
    "/read-all",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description="Mark all notifications as read for a user",
)
async def mark_all_read(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> dict:
    try:
        count = await service.mark_all_read(user_id=user_id)
        return {"updated": count}
    except DatabaseError as e:
        logger.exception(
            "Database error marking all notifications read for user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to mark all notifications as read"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error marking all notifications read for user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/{notification_id}",
    response_model=DeleteNotificationResponse,
    status_code=status.HTTP_200_OK,
    description="Soft-delete a single notification (scoped to user)",
)
async def delete_notification(
    notification_id: UUID4,
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> DeleteNotificationResponse:
    try:
        count = await service.delete_notification(
            notification_id=notification_id, user_id=user_id
        )
        if count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Notification {notification_id} "
                f"not found for user {user_id}",
            )
        return DeleteNotificationResponse(deleted=count)
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.exception(
            "Database error deleting notification_id=%s for user_id=%s",
            notification_id,
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete notification"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error deleting notification_id=%s for user_id=%s",
            notification_id,
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/by-user/{user_id}",
    response_model=DeleteAllNotificationsResponse,
    status_code=status.HTTP_200_OK,
    description="Soft-delete all notifications for a user",
)
async def delete_all_notifications(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> DeleteAllNotificationsResponse:
    try:
        count = await service.delete_all_notifications(user_id=user_id)
        return DeleteAllNotificationsResponse(deleted=count)
    except DatabaseError as e:
        logger.exception(
            "Database error deleting all notifications for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to delete notifications"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error deleting all notifications for user_id=%s",
            user_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


# ── Device Tokens ────────────────────────────────────────────────────────────


@router.post(
    "/device-tokens",
    response_model=RegisterDeviceTokenResponse,
    status_code=status.HTTP_201_CREATED,
    description="Register or update a FCM device token",
)
async def register_device_token(
    request: RegisterDeviceTokenRequest,
    service: Service = Depends(get_service),
) -> RegisterDeviceTokenResponse:
    try:
        return await service.register_device_token(request=request)
    except DatabaseError as e:
        logger.exception(
            "Database error registering device token for user_id=%s",
            request.user_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to register device token"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error registering device token for user_id=%s",
            request.user_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/device-tokens/by-user/{user_id}",
    response_model=ListDeviceTokensResponse,
    status_code=status.HTTP_200_OK,
    description="Get device tokens for a user. Pass active_only=false"
    "to include deactivated tokens.",
)
async def get_device_tokens_by_user(
    user_id: UUID4,
    active_only: bool = True,
    service: Service = Depends(get_service),
) -> ListDeviceTokensResponse:
    try:
        return await service.get_device_tokens_by_user(
            user_id=user_id, active_only=active_only
        )
    except DatabaseError as e:
        logger.exception(
            "Database error fetching device tokens for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch device tokens"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error fetching device tokens for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/device-tokens/by-token/{token}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description="Remove a device token by FCM token value",
)
async def remove_device_token_by_token(
    token: str,
    service: Service = Depends(get_service),
) -> dict:
    try:
        count = await service.remove_device_token_by_token(token=token)
        if count == 0:
            raise HTTPException(
                status_code=404, detail="Device token not found"
            )
        return {"deleted": count}
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.exception("Database error removing device token=%s", token)
        raise HTTPException(
            status_code=500, detail="Failed to remove device token"
        ) from e
    except Exception as e:
        logger.exception("Unexpected error removing device token=%s", token)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch(
    "/device-tokens/deactivate-by-session/{session_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description="Soft-deactivate device tokens for a session (on logout)",
)
async def deactivate_device_tokens_by_session(
    session_id: UUID4,
    service: Service = Depends(get_service),
) -> dict:
    try:
        count = await service.deactivate_device_tokens_by_session(
            session_id=session_id
        )
        return {"deactivated": count}
    except DatabaseError as e:
        logger.exception(
            "Database error deactivating device tokens for session_id=%s",
            session_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to deactivate device tokens"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error deactivating device tokens for session_id=%s",
            session_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/device-tokens/by-session/{session_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description="Hard-delete all device tokens for a session (on revoke)",
)
async def remove_device_tokens_by_session(
    session_id: UUID4,
    service: Service = Depends(get_service),
) -> dict:
    try:
        count = await service.remove_device_tokens_by_session(
            session_id=session_id
        )
        return {"deleted": count}
    except DatabaseError as e:
        logger.exception(
            "Database error removing device tokens for session_id=%s",
            session_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to remove device tokens"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error removing device tokens for session_id=%s",
            session_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/device-tokens/by-user/{user_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description="Remove all device tokens for a user",
)
async def remove_device_tokens_by_user(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> dict:
    try:
        count = await service.remove_device_tokens_by_user(user_id=user_id)
        return {"deleted": count}
    except DatabaseError as e:
        logger.exception(
            "Database error removing device tokens for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to remove device tokens"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error removing device tokens for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


# ── Maintenance ───────────────────────────────────────────────────────────────


@router.post(
    "/purge",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description="Hard-delete all notification rows older than the given days",
)
async def purge_old_notifications(
    older_than_days: int,
    service: Service = Depends(get_service),
) -> dict:
    try:
        count = await service.purge_old_notifications(
            older_than_days=older_than_days
        )
        return {"deleted": count}
    except DatabaseError as e:
        logger.exception(
            "Database error purging notifications older than %d days",
            older_than_days,
        )
        raise HTTPException(
            status_code=500, detail="Failed to purge old notifications"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error purging notifications older than %d days",
            older_than_days,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


# ── Notification Preferences ─────────────────────────────────────────────────


@router.put(
    "/preferences",
    response_model=GetPreferenceResponse,
    status_code=status.HTTP_200_OK,
    description="Insert or update a notification preference",
)
async def upsert_preference(
    request: UpsertPreferenceRequest,
    service: Service = Depends(get_service),
) -> GetPreferenceResponse:
    try:
        return await service.upsert_preference(request=request)
    except DatabaseError as e:
        logger.exception(
            "Database error upserting preference for user_id=%s type=%s",
            request.user_id,
            request.notification_type,
        )
        raise HTTPException(
            status_code=500, detail="Failed to update notification preference"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error upserting preference for user_id=%s type=%s",
            request.user_id,
            request.notification_type,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/preferences",
    response_model=ListPreferencesResponse,
    status_code=status.HTTP_200_OK,
    description="Get all notification preference overrides for a user",
)
async def get_preferences_by_user(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> ListPreferencesResponse:
    try:
        return await service.get_preferences_by_user(user_id=user_id)
    except DatabaseError as e:
        logger.exception(
            "Database error fetching preferences for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Failed to fetch notification preferences"
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error fetching preferences for user_id=%s", user_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
