import logging

from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_profile.notifications import (
    NotificationsRepository as Repository,
)
from app.schemas.user_profile.notifications import (
    CreateNotificationRequest,
    CreateNotificationResponse,
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

logger = logging.getLogger(__name__)


class NotificationsService:
    """Service class for notifications, device_tokens, and
    notification_preferences tables."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    # ── Notifications ──────────────────────────────────────────────────────

    async def create_notification(
        self, request: CreateNotificationRequest
    ) -> CreateNotificationResponse:
        return await self.repository.create_notification(request=request)

    async def create_notifications_bulk(
        self, requests: list[CreateNotificationRequest]
    ) -> list[CreateNotificationResponse]:
        return await self.repository.create_notifications_bulk(
            requests=requests
        )

    async def list_notifications(
        self,
        user_id: UUID4,
        is_read: bool | None = None,
        max_age_days: int = 90,
        page: int = 1,
        limit: int = 20,
    ) -> ListNotificationsResponse:
        return await self.repository.list_notifications(
            user_id=user_id,
            is_read=is_read,
            max_age_days=max_age_days,
            page=page,
            limit=limit,
        )

    async def unread_count(
        self, user_id: UUID4, max_age_days: int = 90
    ) -> UnreadCountResponse:
        return await self.repository.unread_count(
            user_id=user_id, max_age_days=max_age_days
        )

    async def mark_read(
        self, notification_id: UUID4, user_id: UUID4
    ) -> MarkReadResponse:
        return await self.repository.mark_read(
            notification_id=notification_id, user_id=user_id
        )

    async def mark_all_read(self, user_id: UUID4) -> int:
        return await self.repository.mark_all_read(user_id=user_id)

    async def delete_notification(
        self, notification_id: UUID4, user_id: UUID4
    ) -> int:
        return await self.repository.delete_notification(
            notification_id=notification_id, user_id=user_id
        )

    async def delete_all_notifications(self, user_id: UUID4) -> int:
        return await self.repository.delete_all_notifications(user_id=user_id)

    # ── Device Tokens ──────────────────────────────────────────────────────

    async def register_device_token(
        self, request: RegisterDeviceTokenRequest
    ) -> RegisterDeviceTokenResponse:
        return await self.repository.register_device_token(request=request)

    async def get_device_tokens_by_user(
        self, user_id: UUID4, active_only: bool = True
    ) -> ListDeviceTokensResponse:
        return await self.repository.get_device_tokens_by_user(
            user_id=user_id, active_only=active_only
        )

    async def remove_device_token_by_token(self, token: str) -> int:
        return await self.repository.remove_device_token_by_token(token=token)

    async def deactivate_device_tokens_by_session(
        self, session_id: UUID4
    ) -> int:
        return await self.repository.deactivate_device_tokens_by_session(
            session_id=session_id
        )

    async def remove_device_tokens_by_session(self, session_id: UUID4) -> int:
        return await self.repository.remove_device_tokens_by_session(
            session_id=session_id
        )

    async def remove_device_tokens_by_user(self, user_id: UUID4) -> int:
        return await self.repository.remove_device_tokens_by_user(
            user_id=user_id
        )

    # ── Notification Preferences ───────────────────────────────────────────

    async def upsert_preference(
        self, request: UpsertPreferenceRequest
    ) -> GetPreferenceResponse:
        return await self.repository.upsert_preference(request=request)

    async def get_preferences_by_user(
        self, user_id: UUID4
    ) -> ListPreferencesResponse:
        return await self.repository.get_preferences_by_user(user_id=user_id)
