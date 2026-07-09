"""admin_incident_report_reads

Revision ID: a49c88181154
Revises: e2c7a1b04f93
Create Date: 2026-07-08 23:50:54.315524

Creates ``core.admin_incident_report_reads`` — junction table that tracks
which admin has read (or cleared) each incident report.  One row per
(admin, report) pair; ``is_deleted=true`` means the admin cleared the row.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "a49c88181154"
down_revision: Union[str, None] = "e2c7a1b04f93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ``core.admin_incident_report_reads``.

    Also adds ``last_reminded_at`` to ``core.requests`` for remind-admin
    cooldown tracking.
    """
    op.add_column(
        "requests",
        sa.Column(
            "last_reminded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="core",
    )

    op.create_table(
        "admin_incident_report_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column(
            "incident_report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.incidentreport.id"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "admin_id",
            "incident_report_id",
            name="uq_admin_incident_report_reads_admin_report",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_admin_incident_report_reads_admin_id",
        "admin_incident_report_reads",
        ["admin_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_admin_incident_report_reads_incident_report_id",
        "admin_incident_report_reads",
        ["incident_report_id"],
        schema="core",
    )


def downgrade() -> None:
    """Drop ``core.admin_incident_report_reads`` and revert requests column."""
    op.drop_index(
        "ix_core_admin_incident_report_reads_incident_report_id",
        table_name="admin_incident_report_reads",
        schema="core",
    )
    op.drop_index(
        "ix_core_admin_incident_report_reads_admin_id",
        table_name="admin_incident_report_reads",
        schema="core",
    )
    op.drop_table("admin_incident_report_reads", schema="core")
    op.drop_column("requests", "last_reminded_at", schema="core")
