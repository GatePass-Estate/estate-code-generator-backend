import logging

from sqlalchemy import Column, Boolean, Enum
from app.models.base import BaseModelDB
from app.schemas.user_profile.users import UserRole

logger = logging.getLogger(__name__)


class RolePermission(BaseModelDB):
    """
    SQLAlchemy model for roles and their permissions.

    Attributes:
        role_name (UserRole): Role enum key.
        can_*: Boolean flags for permissions per role.
    """

    __tablename__ = "role_permission"
    __table_args__ = {"schema": "core"}

    role_name = Column(
        Enum(UserRole, name="userrole", schema="core", create_type=False),
        nullable=False,
        unique=True,
    )

    can_register_admin = Column(Boolean, default=False)
    can_register_users = Column(Boolean, default=False)
    can_set_household_limits = Column(Boolean, default=False)
    can_generate_code = Column(Boolean, default=False)
    can_validate_code = Column(Boolean, default=False)
    can_remove_admin = Column(Boolean, default=False)
    can_transfer_admin = Column(Boolean, default=False)
    can_add_household_member = Column(Boolean, default=False)
