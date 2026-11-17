import logging

from sqlalchemy import (
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModelDB
from app.schemas.user_profile.user_documents import (
    DocumentStatus,
    DocumentType,
)

logger = logging.getLogger(__name__)


class UserDocuments(BaseModelDB):
    """
    SQLAlchemy model for user profile documents stored in GCS.

    Multiple rows per (user_id, document_type) are allowed for history, but
    only one active (non-deleted) row per pair at a time. Object paths are
    stable GCS keys; signed URLs are generated on demand and never persisted.
    """

    __tablename__ = "user_documents"
    __table_args__ = (
        Index(
            "uq_core_user_documents_user_type_status_active",
            "user_id",
            "document_type",
            unique=True,
            postgresql_where=text(
                "is_deleted = false "
                "AND document_status = 'active' "
                "AND document_type IN ('profile_picture', 'id_card')"
            ),
        ),
        Index(
            "uq_core_user_documents_user_type_status_pending",
            "user_id",
            "document_type",
            unique=True,
            postgresql_where=text(
                "is_deleted = false "
                "AND document_status = 'pending' "
                "AND document_type IN ('profile_picture', 'id_card')"
            ),
        ),
        {"schema": "core"},
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("core.estates.id"),
        nullable=False,
        index=True,
    )
    document_type = Column(
        Enum(
            DocumentType,
            name="documenttype",
            schema="core",
            create_type=False,
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=False,
    )
    gcs_object_path = Column(String, nullable=False, unique=True)
    content_type = Column(String, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    original_filename = Column(String, nullable=True)
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id"),
        nullable=False,
    )
    document_status = Column(
        Enum(
            DocumentStatus,
            name="documentstatus",
            schema="core",
            create_type=False,
            values_callable=lambda obj: [m.value for m in obj],
        ),
        nullable=True,
    )
