import logging

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class EstateSubscription(BaseModelDB):
    """
    Estate subscription assignment to a tier.
    """

    __tablename__ = "estate_subscription"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=False
    )
    tier_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.subscription_tier.id"),
        nullable=False,
    )
    status = Column(String, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    auto_renew = Column(Boolean, nullable=False, server_default="true")
    covered_users = Column(Integer, nullable=False, server_default="1")
    over_cap_locked = Column(Boolean, nullable=False, server_default="false")
    entitlements = Column(JSONB, nullable=True)
    paystack_subscription_code = Column(String, nullable=True)
    paystack_customer_code = Column(String, nullable=True)
    renew_attempt_count = Column(Integer, nullable=False, server_default="0")
    last_renewal_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_renewal_failure_reason = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
