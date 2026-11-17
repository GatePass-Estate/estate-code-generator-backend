import logging

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB
from app.schemas.user_profile.notifications import (
    DevicePlatform,
    NotificationType,
)

logger = logging.getLogger(__name__)


class Notifications(BaseModelDB):
    """
    SQLAlchemy model for notifications table.

    Attributes:
        user_id (UUID): Recipient user.
        type (NotificationType): Notification category.
        title (str): Short display title.
        body (str): Full notification body.
        is_read (bool): Whether the recipient has read this notification.
        metadata (dict): Optional JSON payload for deep-linking.
    """

    __tablename__ = "notifications"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    type = Column(
        Enum(
            NotificationType,
            name="notificationtype",
            schema="core",
            create_type=False,
        ),
        nullable=False,
    )
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    payload = Column(JSONB, nullable=True)


class DeviceTokens(BaseModelDB):
    """
    SQLAlchemy model for device_tokens table.

    Attributes:
        user_id (UUID): Owning user.
        session_id (UUID): Session the token was registered with (nullable).
        token (str): FCM registration token (unique).
        platform (DevicePlatform): Target platform.
    """

    __tablename__ = "device_tokens"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    token = Column(String, nullable=False, unique=True)
    platform = Column(
        Enum(
            DevicePlatform,
            name="deviceplatform",
            schema="core",
            create_type=False,
        ),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)


class NotificationPreferences(BaseModelDB):
    """
    SQLAlchemy model for notification_preferences table.

    Stores explicit user overrides only — absence of a row means defaults
    apply.

    Attributes:
        user_id (UUID): Owning user.
        notification_type (NotificationType): The notification type being
            configured.
        push_enabled (bool): Whether push delivery is enabled (default True).
        email_enabled (bool): Whether email delivery is enabled (default True).
    """

    __tablename__ = "notification_preferences"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    notification_type = Column(
        Enum(
            NotificationType,
            name="notificationtype",
            schema="core",
            create_type=False,
        ),
        nullable=False,
    )
    push_enabled = Column(Boolean, nullable=False, default=True)
    email_enabled = Column(Boolean, nullable=False, default=True)
