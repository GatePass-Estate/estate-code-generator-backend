"""add residents_log table

Revision ID: b033dd6f9794
Revises: e68c04e61eb0
Create Date: 2026-02-02 00:11:22.753501

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "b033dd6f9794"
down_revision: Union[str, None] = "e68c04e61eb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "residentlog",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id",
            sa.UUID,
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column(
            "estate_id",
            sa.UUID,
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column("hashed_code", sa.String, nullable=False),
        sa.Column(
            "security_id",
            sa.UUID,
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column(
            "access_time",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
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
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_residentlog_id",
        table_name="residentlog",
        columns=["id"],
        unique=True,
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_core_residentlog_id",
        table_name="residentlog",
        schema="core",
    )
    op.drop_table("residentlog", schema="core")
