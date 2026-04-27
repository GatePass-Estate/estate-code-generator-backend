"""Add prediction-result table linked to feature snapshots.

Revision ID: 628632808fd8
Revises: 9407c21d919e
Create Date: 2026-04-26 21:21:42.688751

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "628632808fd8"
down_revision: Union[str, None] = "9407c21d919e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_prediction_type_enum = postgresql.ENUM(
    "VisitorAnomalyRealtime",
    "ResidentAnomalyRealtime",
    name="prediction_type",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Create prediction-type enum and ``core.predictionresult`` table."""
    _prediction_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "predictionresult",
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
        sa.Column(
            "feature_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.logfeatureengineering.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visitor_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.visitorlog.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "resident_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.residentlog.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("prediction_type", _prediction_type_enum, nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "(visitor_log_id IS NOT NULL AND resident_log_id IS NULL) OR "
            "(resident_log_id IS NOT NULL AND visitor_log_id IS NULL)",
            name="ck_pr_anchor_log",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "uq_pr_feature_log_prediction_type",
        "predictionresult",
        ["feature_log_id", "prediction_type"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    """Drop ``core.predictionresult`` and its enum."""
    op.drop_index(
        "uq_pr_feature_log_prediction_type",
        table_name="predictionresult",
        schema="core",
    )
    op.drop_table("predictionresult", schema="core")
    _prediction_type_enum.drop(op.get_bind(), checkfirst=True)
