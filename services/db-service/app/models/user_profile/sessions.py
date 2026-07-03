import logging

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class Sessions(BaseModelDB):
    """
    SQLAlchemy model for sessions table.

    Attributes:
        user_id (UUID): Reference to the user.
        device_name (str): Human-readable device name from User-Agent.
        ip_address (str): IP address of the client at login.
        last_active_at (DateTime): Last time this session was used.
        expires_at (DateTime): When this session token expires.
        is_2fa_verified (bool): Whether 2FA was completed for this session.
    """

    __tablename__ = "sessions"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    device_name = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_2fa_verified = Column(Boolean, default=False, nullable=False)
