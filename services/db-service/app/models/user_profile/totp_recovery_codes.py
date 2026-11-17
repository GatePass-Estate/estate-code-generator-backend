import logging

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class TotpRecoveryCodes(BaseModelDB):
    """
    SQLAlchemy model for totp_recovery_codes table.

    Attributes:
        user_id (UUID): Reference to the user.
        code_hash (str): Bcrypt hash of the recovery code.
        used_at (DateTime): When this code was consumed (null = unused).
    """

    __tablename__ = "totp_recovery_codes"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    code_hash = Column(String, nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
