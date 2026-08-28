import logging

from sqlalchemy import Boolean, Column, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class SubscriptionTier(BaseModelDB):
    """
    Subscription tier catalog with entitlements JSONB defaults.
    """

    __tablename__ = "subscription_tier"
    __table_args__ = {"schema": "core"}

    slug = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    display_order = Column(Integer, nullable=False, server_default="0")
    entitlements = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    included_ai_features = Column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    is_custom = Column(Boolean, nullable=False, server_default="false")
    is_active = Column(Boolean, nullable=False, server_default="true")
    billing_unit_hint = Column(String, nullable=True)
