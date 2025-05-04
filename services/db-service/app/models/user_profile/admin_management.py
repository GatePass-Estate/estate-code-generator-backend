import logging

from sqlalchemy import Column, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class AdminManagement(BaseModelDB):
    """
    Tracks admins within estates.

    Attributes:
        id (UUID): Unique identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        estate_id (UUID): Estate the admin belongs to.
        user_id (UUID): Admin user.
        is_primary (bool): Indicates primary admin.
    """

    __tablename__ = "admin_management"
    __table_args__ = {"schema": "core"}

    estate_id = Column(UUID(as_uuid=True), ForeignKey("core.estates.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("core.users.id"))
    is_primary = Column(Boolean, default=False)
