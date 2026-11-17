import logging

from sqlalchemy import Column, DateTime, String, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB
from app.schemas.user_profile.requests import (
    RequestType,
    Status,
)

logger = logging.getLogger(__name__)


class Requests(BaseModelDB):
    """
    SQLAlchemy model for requests table.

    Attributes:
        id (UUID): Unique identifier for each request.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        resident_id (UUID): Resident making the request.
        estate_id (UUID): Estate of the request.
        request_type (RequestType): Type of change.
        old_value (str): Old value.
        new_value (str): New value.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
    """

    __tablename__ = "requests"
    __table_args__ = {"schema": "core"}

    resident_id = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=False
    )
    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=False
    )
    request_type = Column(
        Enum(
            RequestType, name="requesttype", schema="core", create_type=False
        ),
        nullable=False,
    )
    old_value = Column(String, nullable=False)
    new_value = Column(String, nullable=True)
    status = Column(
        Enum(Status, name="status", schema="core", create_type=False),
        nullable=False,
    )
    reviewed_by = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True
    )
    last_reminded_at = Column(DateTime(timezone=True), nullable=True)
