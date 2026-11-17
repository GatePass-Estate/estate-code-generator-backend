import logging

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class PaymentEvent(BaseModelDB):
    """
    Processed payment provider webhook events.
    """

    __tablename__ = "payment_event"
    __table_args__ = {"schema": "core"}

    provider = Column(String, nullable=False, server_default="paystack")
    event_id = Column(String, nullable=False, unique=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    processed_at = Column(DateTime(timezone=True), nullable=True)
