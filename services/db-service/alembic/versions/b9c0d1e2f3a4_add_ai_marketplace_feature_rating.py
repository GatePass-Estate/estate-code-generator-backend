"""move marketplace ratings into their own table

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-08-29 17:30:00.000000

Drops the parent JSONB ratings blob and stores one row per user rating.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace parent JSONB ratings with ``core.ai_marketplace_feature_rating``."""
    op.drop_column("ai_marketplace_feature", "ratings", schema="core")
    op.create_table(
        "ai_marketplace_feature_rating",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("ai_marketplace_feature_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ai_marketplace_feature_id"],
            ["core.ai_marketplace_feature.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "uq_ai_marketplace_feature_rating_feature_user",
        "ai_marketplace_feature_rating",
        ["ai_marketplace_feature_id", "user_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_ai_marketplace_feature_rating_feature_score",
        "ai_marketplace_feature_rating",
        ["ai_marketplace_feature_id", "score"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    """Drop the ratings table and restore the parent ``ratings`` JSONB column."""
    op.drop_index(
        "ix_ai_marketplace_feature_rating_feature_score",
        table_name="ai_marketplace_feature_rating",
        schema="core",
    )
    op.drop_index(
        "uq_ai_marketplace_feature_rating_feature_user",
        table_name="ai_marketplace_feature_rating",
        schema="core",
    )
    op.drop_table("ai_marketplace_feature_rating", schema="core")
    op.add_column(
        "ai_marketplace_feature",
        sa.Column(
            "ratings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="core",
    )
