import logging

from sqlalchemy import Boolean, Column, String, Text

from app.models.base import BaseModelDB

logger = logging.getLogger(__name__)


class ServiceCatalog(BaseModelDB):
    """
    Non-AI feature catalog definition (no price column).
    """

    __tablename__ = "service_catalog"
    __table_args__ = {"schema": "core"}

    service_key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    limit_type = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
