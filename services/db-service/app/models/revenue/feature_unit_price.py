import logging

from sqlalchemy import Boolean, Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class FeatureUnitPrice(BaseModelDB):
    """
    Country/currency unit price for a service_catalog or ai_feature row.
    """

    __tablename__ = "feature_unit_price"
    __table_args__ = {"schema": "core"}

    country_code = Column(String, nullable=False)
    currency_code = Column(String, nullable=False)
    feature_kind = Column(String, nullable=False)
    service_catalog_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.service_catalog.id"),
        nullable=True,
    )
    ai_feature_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.ai_feature.id"),
        nullable=True,
    )
    feature_unit_price = Column(Numeric(18, 2), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
