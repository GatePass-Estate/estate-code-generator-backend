import logging

from sqlalchemy import Column, String, Enum, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB
from app.schemas.user_profile.users import UserRole

logger = logging.getLogger(__name__)


class Users(BaseModelDB):
    """
    SQLAlchemy model for users table.

    Attributes:
        id (UUID): Unique identifier for each user.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email for authentication.
        phone_number (str): Optional phone number.
        password (str): Hashed password.
        estate_id (UUID): Reference to the estate.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "core"}

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone_number = Column(String, nullable=True)
    password = Column(String, nullable=False)
    estate_id = Column(UUID(as_uuid=True), ForeignKey("core.estates.id"))
    role = Column(
        Enum(UserRole, name="userrole", schema="core", create_type=False),
        nullable=False,
    )
    status = Column(Boolean, default=True)
