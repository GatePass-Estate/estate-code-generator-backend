"""add incident summary generation counter

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u
Create Date: 2026-09-27 14:10:00.000000

One row per estate tracking how many third-party incident summaries
were generated on the stored UTC date.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

revision: str = "q0r1s2t3u4v5"
down_revision: Union[str, None] = "p9q0r1s2t3u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ``core.incident_summary_generation``."""
    op.create_table(
        "incident_summary_generation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "estate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.estates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("generation_date", sa.Date(), nullable=False),
        sa.Column(
            "generation_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default="false",
            nullable=True,
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
            "estate_id",
            name="uq_incident_summary_generation_estate_id",
        ),
        schema="core",
    )
    op.create_index(
        "ix_incident_summary_generation_id",
        "incident_summary_generation",
        ["id"],
        unique=True,
        schema="core",
    )


def downgrade() -> None:
    """Drop ``core.incident_summary_generation``."""
    op.drop_index(
        "ix_incident_summary_generation_id",
        table_name="incident_summary_generation",
        schema="core",
    )
    op.drop_table("incident_summary_generation", schema="core")
