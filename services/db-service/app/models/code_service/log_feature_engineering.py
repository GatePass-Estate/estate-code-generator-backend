"""Persisted engineered feature vectors per log validation and anomaly type."""

import logging

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Enum as SQLEnum,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB
from app.schemas.code_service.log_feature_engineering import (
    AnomalyType,
    LogKind,
)

logger = logging.getLogger(__name__)


class LogFeatureEngineering(BaseModelDB):
    """
    One row per visitor or resident log validation anchor.

    ``features_*`` columns hold the feature dict for that ``AnalysisScope``
    when it was last computed for ``anomaly_type`` (visitor- vs resident-centred
    run).
    """

    __tablename__ = "logfeatureengineering"
    __table_args__ = (
        CheckConstraint(
            "(log_kind = 'visitor' AND visitor_log_id IS NOT NULL AND "
            "resident_log_id IS NULL) OR "
            "(log_kind = 'resident' AND resident_log_id IS NOT NULL AND "
            "visitor_log_id IS NULL)",
            name="ck_lfe_log_kind_anchor",
        ),
        {"schema": "core"},
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
    anomaly_type = Column(
        SQLEnum(
            AnomalyType,
            name="anomaly_type",
            schema="core",
            native_enum=True,
            create_type=False,
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    log_kind = Column(
        SQLEnum(
            LogKind,
            name="log_kind",
            schema="core",
            native_enum=True,
            create_type=False,
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    features_visitor_specific = Column(JSONB, nullable=True)
    features_resident_specific = Column(JSONB, nullable=True)
    features_security_specific = Column(JSONB, nullable=True)
    features_estate_wide = Column(JSONB, nullable=True)
    is_anomalous = Column(Boolean, nullable=False, server_default="false")
