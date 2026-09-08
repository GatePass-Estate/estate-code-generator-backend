"""Add ai_response table and drop predictionresult.ai_summary.

Revision ID: g7h8i9j0k1l2
Revises: e8b4c2d91a70
Create Date: 2026-09-06 11:00:00.000000

Creates ``core.ai_response`` as the shared cache for AI-generated reports.
Each feature uses its own lookup key (prediction id for anomaly, estate
+ date window for incident summary). Tiers are stored together in
``ai_summary`` as ``{"tier1": ..., "tier2": ...}``. Existing
``predictionresult.ai_summary`` values are not copied; move them
manually if needed, then this revision drops the column.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "e8b4c2d91a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ``core.ai_response`` and drop ``predictionresult.ai_summary``."""
    op.create_table(
        "ai_response",
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
            "is_deleted",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column("feature_key", sa.String(), nullable=False),
        sa.Column("lookup_key", sa.String(), nullable=False),
        sa.Column(
            "prediction_result_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.predictionresult.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "estate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.estates.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("from_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("to_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_summary", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "uq_ai_response_feature_lookup",
        "ai_response",
        ["feature_key", "lookup_key"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_core_ai_response_prediction_result_id",
        "ai_response",
        ["prediction_result_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_ai_response_estate_id",
        "ai_response",
        ["estate_id"],
        schema="core",
    )
    op.drop_column("predictionresult", "ai_summary", schema="core")


def downgrade() -> None:
    """Restore ``predictionresult.ai_summary`` and drop ``ai_response``."""
    op.add_column(
        "predictionresult",
        sa.Column("ai_summary", postgresql.JSONB(), nullable=True),
        schema="core",
    )
    op.drop_index(
        "ix_core_ai_response_estate_id",
        table_name="ai_response",
        schema="core",
    )
    op.drop_index(
        "ix_core_ai_response_prediction_result_id",
        table_name="ai_response",
        schema="core",
    )
    op.drop_index(
        "uq_ai_response_feature_lookup",
        table_name="ai_response",
        schema="core",
    )
    op.drop_table("ai_response", schema="core")
