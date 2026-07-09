from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB


class AdminIncidentReportRead(BaseModelDB):
    """
    Tracks per-admin read/clear state for incident reports.

    One row per (admin_id, incident_report_id) pair.
    ``is_deleted=True`` means the admin cleared the row ("Clear All").
    Cleared rows are excluded from the admin's view entirely.
    """

    __tablename__ = "admin_incident_report_reads"
    __table_args__ = (
        UniqueConstraint(
            "admin_id",
            "incident_report_id",
            name="uq_admin_incident_report_reads_admin_report",
        ),
        {"schema": "core"},
    )

    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
        index=True,
    )
    incident_report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.incidentreport.id"),
        nullable=False,
        index=True,
    )
    read_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
    )
