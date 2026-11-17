import logging

from sqlalchemy import Boolean, Column, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class AiFeature(BaseModelDB):
    """
    AI feature catalog definition (no price column).
    """

    __tablename__ = "ai_feature"
    __table_args__ = {"schema": "core"}

    feature_key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_free = Column(Boolean, nullable=False, server_default="false")
    is_active = Column(Boolean, nullable=False, server_default="true")
    tier_benefits = Column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    paystack_plan_code = Column(String, nullable=True)
