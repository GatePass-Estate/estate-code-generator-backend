import logging

from sqlalchemy import Boolean, Column, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class AiMarketplaceFeature(BaseModelDB):
    """Parent marketplace product grouping child ai_feature tiers."""

    __tablename__ = "ai_marketplace_feature"
    __table_args__ = {"schema": "core"}

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    tiers = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
