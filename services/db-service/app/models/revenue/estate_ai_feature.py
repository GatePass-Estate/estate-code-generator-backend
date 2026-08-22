import logging

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class EstateAiFeature(BaseModelDB):
    """
    Per-estate AI feature install/grant row.

    Billing fields (status, expires_at, auto_renew, is_free) are independent
    of is_installed — uninstall must not clear entitlement timestamps.
    """

    __tablename__ = "estate_ai_feature"
    __table_args__ = {"schema": "core"}

    estate_id = Column(
        UUID(as_uuid=True), ForeignKey("core.estates.id"), nullable=False
    )
    ai_feature_id = Column(
        UUID(as_uuid=True), ForeignKey("core.ai_feature.id"), nullable=False
    )
    source = Column(String, nullable=True)
    estate_subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.estate_subscription.id"),
        nullable=True,
    )
    checkout_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.payment_checkout_session.id"),
        nullable=True,
    )
    is_installed = Column(Boolean, nullable=False, server_default="true")
    status = Column(String, nullable=False, server_default="active")
    is_free = Column(Boolean, nullable=False, server_default="false")
    auto_renew = Column(Boolean, nullable=False, server_default="true")
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
