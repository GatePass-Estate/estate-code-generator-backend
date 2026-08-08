import logging

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    ForeignKey,
    DateTime,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class Broadcasts(BaseModelDB):
    """
    SQLAlchemy model for broadcasts table.

    Attributes:
        id (UUID): Unique identifier for each broadcast.
        estate_id (UUID): Broadcast estate (NULL for root broadcasts).
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full broadcast message.
        audience (List[str]): Role-based audience (e.g. ["resident"]).
        priority (str): Delivery priority — LOW, MEDIUM, or HIGH.
        category (str): Broadcast category — BROADCAST or AD.
        sender_name (str): Optional custom sender display name.
        attachment_url (str): Optional URL of the attachment.
        status (bool): Active/inactive status.
        expires_at (DateTime): UTC timestamp of expiration.
    """

    __tablename__ = "broadcasts"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=True
    )
    sender_id = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=False
    )
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    audience = Column(ARRAY(Text), nullable=False)
    priority = Column(
        Enum(
            "LOW",
            "MEDIUM",
            "HIGH",
            name="broadcast_priority",
            schema="core",
            create_type=False,
        ),
        nullable=False,
        default="LOW",
    )
    category = Column(
        Enum(
            "BROADCAST",
            "AD",
            name="broadcast_category",
            schema="core",
            create_type=False,
        ),
        nullable=False,
        default="BROADCAST",
    )
    sender_name = Column(String, nullable=True)
    attachment_url = Column(String, nullable=True)
    status = Column(Boolean, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
