"""Add user_documents table for GCS-backed profile picture and ID card metadata.

Revision ID: f3a8c2d91e4b
Revises: 643ae5b5facc
Create Date: 2026-07-05 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "f3a8c2d91e4b"
down_revision: Union[str, None] = "643ae5b5facc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_documenttype_enum = postgresql.ENUM(
    "profile_picture",
    "id_card",
    name="documenttype",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Create documenttype enum and core.user_documents table."""
    _documenttype_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "estate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column("document_type", _documenttype_enum, nullable=False),
        sa.Column("gcs_object_path", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gcs_object_path",
            name="uq_core_user_documents_gcs_object_path",
        ),
        schema="core",
    )
    op.create_index(
        "uq_core_user_documents_user_id_document_type_active",
        "user_documents",
        ["user_id", "document_type"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_core_user_documents_user_id",
        "user_documents",
        ["user_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_user_documents_estate_id",
        "user_documents",
        ["estate_id"],
        schema="core",
    )


def downgrade() -> None:
    """Drop core.user_documents and documenttype enum."""
    op.drop_index(
        "uq_core_user_documents_user_id_document_type_active",
        table_name="user_documents",
        schema="core",
    )
    op.drop_index(
        "ix_core_user_documents_estate_id",
        table_name="user_documents",
        schema="core",
    )
    op.drop_index(
        "ix_core_user_documents_user_id",
        table_name="user_documents",
        schema="core",
    )
    op.drop_table("user_documents", schema="core")
    _documenttype_enum.drop(op.get_bind(), checkfirst=True)
