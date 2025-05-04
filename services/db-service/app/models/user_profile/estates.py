import logging

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class Estates(BaseModelDB):
    """
    SQLAlchemy model for registered estates.

    Attributes:
        id (UUID): Unique estate identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): Soft delete.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        name (str): Estate name.
        location (str): Estate location.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    __tablename__ = "estates"
    __table_args__ = {"schema": "core"}

    name = Column(String, nullable=False)
    location = Column(Text, nullable=False)
    primary_admin_id = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True
    )
