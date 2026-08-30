"""Persisted prediction payload linked to a feature-engineering row."""

import logging

from sqlalchemy import CheckConstraint, Column, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB
from app.schemas.code_service.log_feature_engineering import PredictionType

logger = logging.getLogger(__name__)


class PredictionResult(BaseModelDB):
    """Prediction payload row tied to one feature-log snapshot."""

    __tablename__ = "predictionresult"
    __table_args__ = (
        CheckConstraint(
            "(visitor_log_id IS NOT NULL AND resident_log_id IS NULL) OR "
            "(resident_log_id IS NOT NULL AND visitor_log_id IS NULL)",
            name="ck_pr_anchor_log",
        ),
        {"schema": "core"},
    )

    feature_log_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.logfeatureengineering.id", ondelete="CASCADE"),
        nullable=False,
    )
    visitor_log_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.visitorlog.id", ondelete="CASCADE"),
        nullable=True,
    )
    resident_log_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.residentlog.id", ondelete="CASCADE"),
        nullable=True,
    )
    prediction_type = Column(
        SQLEnum(
            PredictionType,
            name="prediction_type",
            schema="core",
            native_enum=True,
            create_type=False,
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    # Stored as {"result": <prediction payload>} to keep room for metadata.
    result = Column(JSONB, nullable=False)
    # Cached summaries: {"tier1": in-house report, "tier2": LLM report}.
    ai_summary = Column(JSONB, nullable=True)
