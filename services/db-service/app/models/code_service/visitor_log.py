import logging

from sqlalchemy import Column, DateTime, Enum, String, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB
from app.schemas.code_service.visitor_log import Relation

logger = logging.getLogger(__name__)


class VisitorLog(BaseModelDB):
    """
    SQLAlchemy model for workflow steps table in the database.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        user_id (UUID): Reference to the visited resident.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, spouse,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """

    __tablename__ = "visitorlog"
    __table_args__ = {"schema": "core"}

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    visitor_fullname = Column(
        type_=String,
        nullable=False,
    )
    relationship_with_resident = Column(
        type_=Enum(
            Relation,
            name="agent_type",
            schema="workflows",
            create_type=False,
        ),
        nullable=False,
        doc="Category of the step",
    )
    hashed_code = Column(
        type_=String,
        nullable=False,
    )
    security_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    visit_time = Column(
        type_=DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        doc="UTC Timestamp of visit validation",
    )
