"""One daily third-party incident-summary slot per estate."""

from sqlalchemy import Column, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB


class IncidentSummaryGeneration(BaseModelDB):
    """
    How many third-party incident summaries an estate has generated today.

    One row per estate. ``generation_date`` is the UTC calendar date the
    counter was last moved. A new UTC date resets ``generation_count``
    to 1 on the next generation.
    """

    __tablename__ = "incident_summary_generation"
    __table_args__ = (
        UniqueConstraint(
            "estate_id",
            name="uq_incident_summary_generation_estate_id",
        ),
        {"schema": "core"},
    )

    estate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.estates.id", ondelete="CASCADE"),
        nullable=False,
    )
    generation_date = Column(Date, nullable=False)
    generation_count = Column(Integer, nullable=False, server_default="0")
