import logging

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class PaymentChargeRetry(BaseModelDB):
    """
    Tracks self-managed charge retry schedules for failed Paystack
    subscription renewals.  One row per failed billing period.
    """

    __tablename__ = "payment_charge_retry"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=False
    )
    target_type = Column(String, nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False)
    paystack_subscription_code = Column(String, nullable=False)
    billing_period_key = Column(String, nullable=False, unique=True)
    amount_kobo = Column(BigInteger, nullable=False)
    currency_code = Column(String, nullable=False, server_default="NGN")
    authorization_code = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default="pending")
    attempt_number = Column(Integer, nullable=False, server_default="0")
    max_attempts = Column(Integer, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)
    last_gateway_response = Column(Text, nullable=True)
    last_provider_reference = Column(String, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
