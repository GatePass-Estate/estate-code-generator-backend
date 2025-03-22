import logging
import uuid

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

logger = logging.getLogger(__name__)


class BaseModelDB(Base):
    """
    Base model for all primitive models, providing common fields and CRUD
    operations.

    Attributes:
        id (UUID): ID of the item.
        created_at (DateTime): Time when the item was created.
        updated_at (DateTime): Time when the item was last updated.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
    """

    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        unique=True,
        nullable=False,
        default=uuid.uuid4,
    )
    created_at = Column(
        type_=DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        doc="UTC Timestamp when the record was created",
    )
    updated_at = Column(
        type_=DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        onupdate=func.timezone("UTC", func.now()),
        doc="UTC Timestamp when the record was last updated",
    )
    deleted_at = Column(
        type_=DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="UTC Timetamp when the record was (soft) deleted",
    )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}(\n"
            + ",\n".join([f"{key}={val}" for key, val in vars(self).items()])
            + "\n)"
        )

    def update(self, **kwargs):
        """
        Update the model with the provided keyword arguments.

        Args:
            **kwargs: Keyword arguments to update the model with.
        """
        for field, value in kwargs.items():
            if hasattr(self, field):
                setattr(self, field, value)
        return self
