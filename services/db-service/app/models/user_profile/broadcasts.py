import logging

from sqlalchemy import Column, String, Enum, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB
from app.schemas.user_profile.broadcasts import Audience

logger = logging.getLogger(__name__)


class Broadcasts(BaseModelDB):
    """
    SQLAlchemy model for broadcasts table.

    Attributes:
        id (UUID): Unique identifier for each broadcast.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        estate_id (UUID): Broadcast estate.
        sender_id (UUID): User who created the broadcast.
        title (str): Broadcast title.
        message (str): Full Broadcast message.
        audience (Audience): Audience for the broadcast.
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
    audience = Column(
        Enum(Audience, name="audience", schema="core", create_type=False),
        nullable=False,
    )
    attachment_url = Column(String, nullable=True)
    status = Column(Boolean, nullable=False)
    expires_at = Column(DateTime, nullable=True)
