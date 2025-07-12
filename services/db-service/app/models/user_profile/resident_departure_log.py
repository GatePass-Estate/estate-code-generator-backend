import logging

from sqlalchemy import Column, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class ResidentDepartureLog(BaseModelDB):
    """
    Tracks residents leaving the estate.

    Attributes:
        id (UUID): Unique identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        admin_id (UUID): Admin who approved the departure.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
    """

    __tablename__ = "resident_departure_log"
    __table_args__ = {"schema": "core"}

    user_id = Column(UUID(as_uuid=True), ForeignKey("core.users.id"))
    estate_id = Column(UUID(as_uuid=True), ForeignKey("core.estates.id"))
    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=True,
    )
    departure_time = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(Text, nullable=True)
