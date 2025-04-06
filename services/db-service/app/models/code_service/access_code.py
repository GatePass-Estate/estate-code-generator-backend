from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB


class AccessCode(BaseModelDB):
    """
    SQLAlchemy model for workflows table in the database.

    Attributes:
        id (UUID): Unique identifier for the access code.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        is_deleted (Optional[Boolean]): Flag to indicate if the item is (soft)
            deleted.
        user_id (UUID): Reference to the resident generating code.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Securely stored hash of access code.
        valid_until (DateTime): Expiration timestamp for the access code.
    """

    __tablename__ = "accesscode"
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
    valid_until = Column(
        type_=DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        doc="Expiration timestamp for the access code",
    )
