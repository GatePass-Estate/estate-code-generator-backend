import logging

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class TrustedDevices(BaseModelDB):
    """
    SQLAlchemy model for trusted_devices table.

    Stores cryptographic device trust tokens so that device familiarity
    persists across logouts and session expiry.  Replaces the old
    IP-based familiarity check.

    Attributes:
        user_id (UUID): Reference to the user who owns this device.
        token_hash (str): SHA-256 hex digest of the raw device token.
        device_label (str): Human-readable device name (from User-Agent).
        ip_address (str): IP address at the time of token creation.
        last_seen_at (DateTime): Last time this device token was used.
        expires_at (DateTime): Fixed expiry (never extended).
        is_revoked (bool): Whether this device has been revoked.
        revoked_at (DateTime): When the device was revoked.
    """

    __tablename__ = "trusted_devices"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    token_hash = Column(Text, nullable=False, unique=True)
    device_label = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
