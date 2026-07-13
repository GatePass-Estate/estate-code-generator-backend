"""household rework: add name/head_user_id,drop primary_resident_id/max_members

Revision ID: 6ce3f93d3c37
Revises: 9b3a86d81970
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6ce3f93d3c37"
down_revision: Union[str, None] = "9b3a86d81970"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add name column (nullable; existing rows get a placeholder)
    op.add_column(
        "household",
        sa.Column("name", sa.String(), nullable=True),
        schema="core",
    )
    op.execute("UPDATE core.household SET name = 'Household'")

    # 2. Add head_user_id column
    op.add_column(
        "household",
        sa.Column(
            "head_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="core",
    )
    op.create_foreign_key(
        "fk_household_head_user_id",
        "household",
        "users",
        ["head_user_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )

    # 3. Copy existing primary_resident_id → head_user_id
    op.execute("UPDATE core.household SET head_user_id = primary_resident_id")

    # 4. Drop primary_resident_id (FK constraint first)
    op.drop_constraint(
        "household_primary_resident_id_fkey",
        "household",
        type_="foreignkey",
        schema="core",
    )
    op.drop_column("household", "primary_resident_id", schema="core")

    # 5. Drop max_members
    op.drop_column("household", "max_members", schema="core")

    # 6. Add new notification types for household head events
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'HOUSEHOLD_HEAD_ASSIGNED'"
    )
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'HOUSEHOLD_NEEDS_HEAD'"
    )


def downgrade() -> None:
    # Re-add max_members
    op.add_column(
        "household",
        sa.Column(
            "max_members",
            sa.Integer(),
            nullable=True,
            server_default="10",
        ),
        schema="core",
    )

    # Re-add primary_resident_id
    op.add_column(
        "household",
        sa.Column(
            "primary_resident_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="core",
    )
    op.create_foreign_key(
        "household_primary_resident_id_fkey",
        "household",
        "users",
        ["primary_resident_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )
    op.execute("UPDATE core.household SET primary_resident_id = head_user_id")

    # Drop head_user_id
    op.drop_constraint(
        "fk_household_head_user_id",
        "household",
        type_="foreignkey",
        schema="core",
    )
    op.drop_column("household", "head_user_id", schema="core")

    # Drop name
    op.drop_column("household", "name", schema="core")

    # Note: PostgreSQL does not support removing enum values —
    # HOUSEHOLD_HEAD_ASSIGNED and HOUSEHOLD_NEEDS_HEAD will remain
    # in core.notificationtype after downgrade.
