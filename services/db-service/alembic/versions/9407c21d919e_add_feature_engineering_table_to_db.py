"""add feature engineering table to DB

Revision ID: 9407c21d919e
Revises: 23816374eb12
Create Date: 2026-04-19 14:11:24.413489

Stores per-validation engineered feature vectors (one row per visitor or resident
log id), keyed by anomaly type, with JSONB columns per ``AnalysisScope``, plus
``is_anomalous`` so reference lookups can exclude past anomalies.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "9407c21d919e"
down_revision: Union[str, None] = "23816374eb12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_log_kind_enum = postgresql.ENUM(
    "visitor",
    "resident",
    name="log_kind",
    schema="core",
    create_type=False,
)

_anomaly_type_enum = postgresql.ENUM(
    "visitor",
    "resident",
    name="anomaly_type",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Create enums and ``core.logfeatureengineering`` table."""
    _log_kind_enum.create(op.get_bind(), checkfirst=True)
    _anomaly_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "logfeatureengineering",
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
        sa.Column("anomaly_type", _anomaly_type_enum, nullable=False),
        sa.Column("log_kind", _log_kind_enum, nullable=False),
        sa.Column(
            "features_visitor_specific",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "features_resident_specific",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "features_security_specific",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "features_estate_wide",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "is_anomalous",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(log_kind = 'visitor' AND visitor_log_id IS NOT NULL AND "
            "resident_log_id IS NULL) OR "
            "(log_kind = 'resident' AND resident_log_id IS NOT NULL AND "
            "visitor_log_id IS NULL)",
            name="ck_lfe_log_kind_anchor",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "uq_lfe_visitor_log_anomaly",
        "logfeatureengineering",
        ["visitor_log_id", "anomaly_type"],
        unique=True,
        schema="core",
        postgresql_where=sa.text(
            "visitor_log_id IS NOT NULL AND is_deleted = false"
        ),
    )
    op.create_index(
        "uq_lfe_resident_log_anomaly",
        "logfeatureengineering",
        ["resident_log_id", "anomaly_type"],
        unique=True,
        schema="core",
        postgresql_where=sa.text(
            "resident_log_id IS NOT NULL AND is_deleted = false"
        ),
    )


def downgrade() -> None:
    """Drop feature engineering table and related indexes."""
    op.drop_index(
        "uq_lfe_resident_log_anomaly",
        table_name="logfeatureengineering",
        schema="core",
    )
    op.drop_index(
        "uq_lfe_visitor_log_anomaly",
        table_name="logfeatureengineering",
        schema="core",
    )
    op.drop_table("logfeatureengineering", schema="core")
    _anomaly_type_enum.drop(op.get_bind(), checkfirst=True)
    _log_kind_enum.drop(op.get_bind(), checkfirst=True)
