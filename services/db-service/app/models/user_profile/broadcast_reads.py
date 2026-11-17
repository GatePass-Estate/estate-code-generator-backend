from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB


class BroadcastReads(BaseModelDB):
    """
    Tracks per-user read state for broadcasts.

    One row per (broadcast_id, user_id) pair.
    """

    __tablename__ = "broadcast_reads"
    __table_args__ = (
        UniqueConstraint(
            "broadcast_id",
            "user_id",
            name="uq_broadcast_reads_broadcast_user",
        ),
        {"schema": "core"},
    )

    broadcast_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.broadcasts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    read_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
    )
    is_dismissed = Column(Boolean, nullable=True, default=False)
