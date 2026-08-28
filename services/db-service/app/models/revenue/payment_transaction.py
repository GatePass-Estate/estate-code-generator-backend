import logging

from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class PaymentTransaction(BaseModelDB):
    """
    Payment ledger row.
    """

    __tablename__ = "payment_transaction"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=False
    )
    checkout_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.payment_checkout_session.id"),
        nullable=True,
    )
    amount = Column(Numeric(18, 2), nullable=False)
    currency_code = Column(String, nullable=False)
    status = Column(String, nullable=False)
    provider_reference = Column(String, nullable=True)
    raw = Column(JSONB, nullable=True)
