import logging

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class AiMarketplaceFeatureRating(BaseModelDB):
    """One user score for a parent marketplace feature."""

    __tablename__ = "ai_marketplace_feature_rating"
    __table_args__ = {"schema": "core"}

    ai_marketplace_feature_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.ai_marketplace_feature.id"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False)
    score = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
