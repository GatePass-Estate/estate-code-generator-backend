import logging

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class PaymentCheckoutSession(BaseModelDB):
    """
    Checkout intent with pricing snapshot.
    """

    __tablename__ = "payment_checkout_session"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=False
    )
    idempotency_key = Column(String, nullable=False, unique=True)
    paystack_reference = Column(String, nullable=True, unique=True)
    status = Column(String, nullable=False, server_default="pending")
    pricing_snapshot = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    amount = Column(Numeric(18, 2), nullable=False)
    currency_code = Column(String, nullable=False)
    country_code = Column(String, nullable=False)
    checkout_kind = Column(String, nullable=False)
    # "metadata" is reserved on Declarative API; map to column name metadata
    session_metadata = Column("metadata", JSONB, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
