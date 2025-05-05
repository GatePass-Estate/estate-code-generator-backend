import logging

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class Household(BaseModelDB):
    """
    Tracks households within estates.

    Attributes:
        id (UUID): Unique identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        estate_id (UUID): Estate the household is in.
        primary_resident_id (UUID): Lead resident in household.
        max_members (int): Max allowed residents.
    """

    __tablename__ = "household"
    __table_args__ = {"schema": "core"}

    estate_id = Column(UUID(as_uuid=True), ForeignKey("core.estates.id"))
    primary_resident_id = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id")
    )
    max_members = Column(Integer, default=10)
