import logging

from sqlalchemy import Column, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class ResidentDepartureLog(BaseModelDB):
    """
    Tracks residents leaving the estate.

    Attributes:
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
    """

    __tablename__ = "resident_departure_log"
    __table_args__ = {"schema": "core"}

    user_id = Column(UUID(as_uuid=True), ForeignKey("core.users.id"))
    estate_id = Column(UUID(as_uuid=True), ForeignKey("core.estates.id"))
    departure_time = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(Text, nullable=True)
