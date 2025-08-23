import logging

from sqlalchemy import Column, String, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB
from app.schemas.user_profile.guests import Gender

logger = logging.getLogger(__name__)


class Guests(BaseModelDB):
    """
    SQLAlchemy model for guests table.

    Attributes:
        id (UUID): Unique identifier for each guest.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        resident_id (UUID): Resident who saved the guest.
        guest_name (str): Full name of the guest.
        guest_phone_number (str): Optional phone number.
        gender (Gender): Gender of the guest.
        relationship (str): Relationship with guest.
    """

    __tablename__ = "guests"
    __table_args__ = {"schema": "core"}

    resident_id = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=False
    )
    guest_name = Column(String, nullable=False)
    guest_phone_number = Column(String, nullable=True)
    gender = Column(
        Enum(Gender, name="gender", schema="core", create_type=False),
        nullable=False,
    )
    relationship = Column(String, nullable=False)
