"""Shared cache for generated AI reports across features."""

import logging

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class AiResponse(BaseModelDB):
    """
    One cached in-house / LLM report for a feature-specific lookup key.

    Anomaly cases use ``prediction_result_id`` as the key. Incident
    summaries use ``estate_id`` plus the request date window. Other
    features store their own ``lookup_key``. Both tiers live in
    ``ai_summary`` as ``{"tier1": ..., "tier2": ...}``.
    """

    __tablename__ = "ai_response"
    __table_args__ = {"schema": "core"}

    feature_key = Column(String, nullable=False)
    lookup_key = Column(String, nullable=False)
    prediction_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.predictionresult.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    estate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.estates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    from_date = Column(DateTime(timezone=True), nullable=True)
    to_date = Column(DateTime(timezone=True), nullable=True)
    ai_summary = Column(JSONB, nullable=True)
