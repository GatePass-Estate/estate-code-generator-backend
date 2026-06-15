import logging

from sqlalchemy import Column, String, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB
from app.schemas.user_profile.estates import EstateType

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
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID): Reference to the primary admin.
        estate_type (EstateType): Type of estate.
    """

    __tablename__ = "estates"
    __table_args__ = {"schema": "core"}

    name = Column(String, nullable=False)
    location = Column(Text, nullable=False)
    lga = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    primary_admin_id = Column(
        UUID(as_uuid=True), ForeignKey("core.users.id"), nullable=True
    )
    estate_type = Column(
        Enum(EstateType, name="estatetype", schema="core", create_type=False),
        nullable=True,
    )
