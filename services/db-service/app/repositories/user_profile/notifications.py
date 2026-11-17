import logging
from datetime import datetime, timedelta, timezone

from pydantic import UUID4
from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError
from app.models import (
    DeviceTokens as DeviceTokensModel,
    NotificationPreferences as PreferencesModel,
    Notifications as NotificationsModel,
)
from app.schemas.user_profile.notifications import (
    CreateNotificationRequest,
    CreateNotificationResponse,
    GetDeviceTokenResponse,
    GetNotificationResponse,
    GetPreferenceResponse,
    ListDeviceTokensResponse,
    ListNotificationsResponse,
    ListPreferencesResponse,
    MarkReadResponse,
    RegisterDeviceTokenRequest,
    RegisterDeviceTokenResponse,
    UnreadCountResponse,
    UpsertPreferenceRequest,
)

logger = logging.getLogger(__name__)


class NotificationsRepository:
    """Repository for the notifications, device_tokens, and
    notification_preferences tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Notifications ──────────────────────────────────────────────────────

    async def create_notification(
        self, request: CreateNotificationRequest
    ) -> CreateNotificationResponse:
        """Insert one notification row."""
        try:
            record = NotificationsModel(
                **request.model_dump(exclude_unset=True)
            )
            self.session.add(record)
            await self.session.flush()
            await self.session.refresh(record)
            return CreateNotificationResponse.model_validate(record.__dict__)
        except SQLAlchemyError as e:
            message = "Database error creating notification"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def create_notifications_bulk(
        self, requests: list[CreateNotificationRequest]
    ) -> list[CreateNotificationResponse]:
        """Insert multiple notification rows in a single flush."""
        try:
            records = [
                NotificationsModel(**r.model_dump(exclude_unset=True))
                for r in requests
            ]
            self.session.add_all(records)
            await self.session.flush()
            for r in records:
                await self.session.refresh(r)
            return [
                CreateNotificationResponse.model_validate(r.__dict__)
                for r in records
            ]
        except SQLAlchemyError as e:
            message = "Database error bulk-creating notifications"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def list_notifications(
        self,
        user_id: UUID4,
        is_read: bool | None = None,
        max_age_days: int = 90,
        page: int = 1,
        limit: int = 20,
    ) -> ListNotificationsResponse:
        """Return paginated notifications for a user within the age window."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)
        query = select(NotificationsModel).where(
            NotificationsModel.user_id == user_id,
            NotificationsModel.created_at >= cutoff,
            NotificationsModel.is_deleted == False,  # noqa E712
        )
        if is_read is not None:
            query = query.where(NotificationsModel.is_read == is_read)

        count_query = select(func.count()).select_from(query.subquery())
        paginated = (
            query.order_by(NotificationsModel.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        try:
            total = await self.session.scalar(count_query)
            records = (
                (await self.session.execute(paginated))
                .unique()
                .scalars()
                .all()
            )
            return ListNotificationsResponse(
                items=[
                    GetNotificationResponse.model_validate(
                        r, from_attributes=True
                    )
                    for r in records
                ],
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            message = "Database error listing notifications"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def unread_count(
        self, user_id: UUID4, max_age_days: int = 90
    ) -> UnreadCountResponse:
        """Count unread notifications for a user within the age window."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)
        query = select(func.count()).where(
            NotificationsModel.user_id == user_id,
            NotificationsModel.is_read == False,  # noqa E712
            NotificationsModel.created_at >= cutoff,
            NotificationsModel.is_deleted == False,  # noqa E712
        )
        try:
            count = await self.session.scalar(query)
            return UnreadCountResponse(count=count or 0)
        except SQLAlchemyError as e:
            message = "Database error counting unread notifications"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def mark_read(
        self, notification_id: UUID4, user_id: UUID4
    ) -> MarkReadResponse:
        """Mark a single notification as read (scoped to the owning user)."""
        try:
            record = await self.session.scalar(
                select(NotificationsModel).where(
                    NotificationsModel.id == notification_id,
                    NotificationsModel.user_id == user_id,
                    NotificationsModel.is_deleted == False,  # noqa E712
                )
            )
            if record is None:
                raise NotFoundError(
                    "Notification %s not found for user" % notification_id
                )
            record.is_read = True
            await self.session.flush()
            await self.session.refresh(record)
            return MarkReadResponse.model_validate(record.__dict__)
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            message = "Database error marking notification read"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def mark_all_read(self, user_id: UUID4) -> int:
        """Mark all unread notifications for a user as read.
        Returns count updated."""
        try:
            result = await self.session.execute(
                update(NotificationsModel)
                .where(
                    NotificationsModel.user_id == user_id,
                    NotificationsModel.is_read == False,  # noqa E712
                    NotificationsModel.is_deleted == False,  # noqa E712
                )
                .values(is_read=True)
            )
            return result.rowcount
        except SQLAlchemyError as e:
            message = "Database error marking all notifications read"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def delete_notification(
        self, notification_id: UUID4, user_id: UUID4
    ) -> int:
        """Soft-delete a single notification scoped to the owning user.
        Returns 1 if deleted, 0 if not found."""
        try:
            record = await self.session.scalar(
                select(NotificationsModel).where(
                    NotificationsModel.id == notification_id,
                    NotificationsModel.user_id == user_id,
                    NotificationsModel.is_deleted == False,  # noqa E712
                )
            )
            if record is None:
                return 0
            record.is_deleted = True
            record.deleted_at = datetime.now(tz=timezone.utc)
            await self.session.flush()
            return 1
        except SQLAlchemyError as e:
            message = "Database error deleting notification"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def purge_old_notifications(self, older_than_days: int) -> int:
        """Hard-delete notification rows older than the given number of days,
        regardless of is_deleted status. Returns count deleted."""
        from sqlalchemy import delete as sa_delete

        cutoff = datetime.now(tz=timezone.utc) - timedelta(
            days=older_than_days
        )
        try:
            result = await self.session.execute(
                sa_delete(NotificationsModel).where(
                    NotificationsModel.created_at < cutoff
                )
            )
            return result.rowcount
        except SQLAlchemyError as e:
            message = "Database error purging old notifications"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def delete_all_notifications(self, user_id: UUID4) -> int:
        """Soft-delete all notifications for a user. Returns count deleted."""
        try:
            result = await self.session.execute(
                update(NotificationsModel)
                .where(
                    NotificationsModel.user_id == user_id,
                    NotificationsModel.is_deleted == False,  # noqa E712
                )
                .values(
                    is_deleted=True,
                    deleted_at=datetime.now(tz=timezone.utc),
                )
            )
            return result.rowcount
        except SQLAlchemyError as e:
            message = "Database error deleting all notifications"
            logger.exception(message)
            raise DatabaseError(message) from e

    # ── Device Tokens ──────────────────────────────────────────────────────

    async def register_device_token(
        self, request: RegisterDeviceTokenRequest
    ) -> RegisterDeviceTokenResponse:
        """Upsert a device token (insert or reactivate + update session
        on conflict)."""
        try:
            stmt = (
                pg_insert(DeviceTokensModel)
                .values(**request.model_dump(exclude_unset=True))
                .on_conflict_do_update(
                    index_elements=["token"],
                    set_={
                        "user_id": request.user_id,
                        "session_id": request.session_id,
                        "platform": request.platform,
                        "is_active": True,
                        "updated_at": func.timezone("UTC", func.now()),
                    },
                )
                .returning(DeviceTokensModel.id, DeviceTokensModel.created_at)
            )
            result = await self.session.execute(stmt)
            row = result.one()
            return RegisterDeviceTokenResponse(
                id=row.id, created_at=row.created_at
            )
        except SQLAlchemyError as e:
            message = "Database error registering device token"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get_device_tokens_by_user(
        self, user_id: UUID4, active_only: bool = True
    ) -> ListDeviceTokensResponse:
        """Return device tokens for a user.
        Filters to active-only by default."""
        try:
            conditions = [
                DeviceTokensModel.user_id == user_id,
                DeviceTokensModel.is_deleted == False,  # noqa E712
            ]
            if active_only:
                conditions.append(  # noqa E712
                    DeviceTokensModel.is_active == True  # noqa E712
                )
            records = (
                (
                    await self.session.execute(
                        select(DeviceTokensModel).where(*conditions)
                    )
                )
                .unique()
                .scalars()
                .all()
            )
            return ListDeviceTokensResponse(
                items=[
                    GetDeviceTokenResponse.model_validate(
                        r, from_attributes=True
                    )
                    for r in records
                ]
            )
        except SQLAlchemyError as e:
            message = "Database error fetching device tokens by user"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def remove_device_token_by_token(self, token: str) -> int:
        """Hard-delete a device token row by FCM token value.
        Returns count deleted."""
        try:
            record = await self.session.scalar(
                select(DeviceTokensModel).where(
                    DeviceTokensModel.token == token
                )
            )
            if record is None:
                return 0
            await self.session.delete(record)
            await self.session.flush()
            return 1
        except SQLAlchemyError as e:
            message = "Database error removing device token"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def deactivate_device_tokens_by_session(
        self, session_id: UUID4
    ) -> int:
        """Soft-deactivate device tokens for a session (logout).
        Returns count."""
        try:
            result = await self.session.execute(
                select(DeviceTokensModel).where(
                    DeviceTokensModel.session_id == session_id,
                    DeviceTokensModel.is_deleted == False,  # noqa E712
                )
            )
            records = result.unique().scalars().all()
            for r in records:
                r.is_active = False
                r.updated_at = func.timezone("UTC", func.now())
            await self.session.flush()
            return len(records)
        except SQLAlchemyError as e:
            message = "Database error deactivating device tokens by session"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def remove_device_tokens_by_session(self, session_id: UUID4) -> int:
        """Hard-delete all device tokens associated with a session.
        Returns count."""
        try:
            records = (
                (
                    await self.session.execute(
                        select(DeviceTokensModel).where(
                            DeviceTokensModel.session_id == session_id
                        )
                    )
                )
                .unique()
                .scalars()
                .all()
            )
            for r in records:
                await self.session.delete(r)
            await self.session.flush()
            return len(records)
        except SQLAlchemyError as e:
            message = "Database error removing device tokens by session"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def remove_device_tokens_by_user(self, user_id: UUID4) -> int:
        """Hard-delete all device tokens for a user. Returns count."""
        try:
            records = (
                (
                    await self.session.execute(
                        select(DeviceTokensModel).where(
                            DeviceTokensModel.user_id == user_id
                        )
                    )
                )
                .unique()
                .scalars()
                .all()
            )
            for r in records:
                await self.session.delete(r)
            await self.session.flush()
            return len(records)
        except SQLAlchemyError as e:
            message = "Database error removing device tokens by user"
            logger.exception(message)
            raise DatabaseError(message) from e

    # ── Notification Preferences ───────────────────────────────────────────

    async def upsert_preference(
        self, request: UpsertPreferenceRequest
    ) -> GetPreferenceResponse:
        """Insert or update a notification preference for a user+type."""
        try:
            stmt = (
                pg_insert(PreferencesModel)
                .values(**request.model_dump())
                .on_conflict_do_update(
                    constraint="uq_notification_preferences_user_type",
                    set_={
                        "push_enabled": request.push_enabled,
                        "email_enabled": request.email_enabled,
                        "updated_at": func.timezone("UTC", func.now()),
                    },
                )
                .returning(PreferencesModel)
            )
            result = await self.session.execute(stmt)
            record = result.scalar_one()
            return GetPreferenceResponse.model_validate(
                record, from_attributes=True
            )
        except SQLAlchemyError as e:
            message = "Database error upserting notification preference"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get_preferences_by_user(
        self, user_id: UUID4
    ) -> ListPreferencesResponse:
        """Return all stored preference overrides for a user."""
        try:
            records = (
                (
                    await self.session.execute(
                        select(PreferencesModel).where(
                            PreferencesModel.user_id == user_id,
                            PreferencesModel.is_deleted == False,  # noqa E712
                        )
                    )
                )
                .unique()
                .scalars()
                .all()
            )
            return ListPreferencesResponse(
                items=[
                    GetPreferenceResponse.model_validate(
                        r, from_attributes=True
                    )
                    for r in records
                ]
            )
        except SQLAlchemyError as e:
            message = "Database error fetching notification preferences"
            logger.exception(message)
            raise DatabaseError(message) from e
