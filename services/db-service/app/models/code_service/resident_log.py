import logging

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class ResidentLog(BaseModelDB):
    """
    SQLAlchemy model for resident log table in the database.

    Attributes:
        id (UUID): Unique identifier for resident log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access.
        access_time (DateTime): Timestamp of resident access validation.
    """

    __tablename__ = "residentlog"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    estate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.estates.id"),
        nullable=False,
    )
    hashed_code = Column(
        type_=String,
        nullable=False,
    )
    security_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    access_time = Column(
        type_=DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        doc="UTC Timestamp of resident access validation",
    )
