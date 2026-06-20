import logging

from sqlalchemy import Column, String, Enum, Boolean, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import BaseModelDB
from app.schemas.user_profile.users import UserRole, Gender

logger = logging.getLogger(__name__)


class Users(BaseModelDB):
    """
    SQLAlchemy model for users table.

    Attributes:
        id (UUID): Unique identifier for each user.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Email address.
        phone_number (str): Optional phone number.
        home_address (str): Home address.
        password (str): Hashed password.
        estate_id (UUID): Reference to the estate.
        household_id (UUID): Reference to the household.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_active_email_estate",
            "email",
            "estate_id",
            unique=True,
            postgresql_where=text("status = TRUE AND is_deleted = FALSE"),
        ),
        Index(
            "uq_users_active_email_no_estate",
            "email",
            unique=True,
            postgresql_where=text(
                "estate_id IS NULL AND status = TRUE AND is_deleted = FALSE"
            ),
        ),
        {"schema": "core"},
    )

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    home_address = Column(String, nullable=False)
    password = Column(String, nullable=False)
    gender = Column(
        Enum(Gender, name="gender", schema="core", create_type=False),
        nullable=False,
    )
    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=True
    )
    household_id = Column(
        UUID(as_uuid=True), ForeignKey("core.household.id"), nullable=True
    )
    role = Column(
        Enum(UserRole, name="userrole", schema="core", create_type=False),
        nullable=False,
    )
    status = Column(Boolean, default=False)
    tos_accepted_version = Column(String, nullable=True)
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=True)
