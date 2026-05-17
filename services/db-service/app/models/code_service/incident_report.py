import logging

from sqlalchemy import (
    ARRAY,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB
from app.schemas.code_service.incident_report import IncidentCategory

logger = logging.getLogger(__name__)


class IncidentReport(BaseModelDB):
    """
    Formal incident report filed against an estate.

    ``category`` is a PostgreSQL array of ``IncidentCategory`` enum values.
    ``custom_category`` holds optional free-text when the taxonomy is insufficient.
    """

    __tablename__ = "incidentreport"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.estates.id"),
        nullable=False,
        index=True,
    )
    reported_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=True,
        index=True,
    )
    title = Column(String(), nullable=True)
    category = Column(
        ARRAY(
            SQLEnum(
                IncidentCategory,
                name="incident_category",
                schema="core",
                native_enum=True,
                create_type=False,
                values_callable=lambda obj: [m.value for m in obj],
            )
        ),
        nullable=False,
        server_default=text("'{}'::core.incident_category[]"),
    )
    custom_category = Column(String(), nullable=True)
    narrative = Column(Text, nullable=False)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
        doc="When the incident occurred or was first observed (UTC).",
    )
