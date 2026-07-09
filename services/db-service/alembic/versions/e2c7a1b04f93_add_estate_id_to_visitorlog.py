"""Add estate_id + full_name to visitorlog and full_name to residentlog.

Revision ID: e2c7a1b04f93
Revises: d1e5f9a2b70c
Create Date: 2026-07-09 10:30:00.000000

The visitor log previously had no estate reference, which made estate-scoped
visitor-history queries impossible. This adds a non-null ``estate_id`` FK,
backfilling existing rows from the visited resident's estate.

It also denormalizes the host resident's ``full_name`` onto both the visitor
and resident logs so history reads return the resident name without an extra
lookup or a join. Existing rows are backfilled from ``core.users``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2c7a1b04f93"
down_revision: Union[str, None] = "d1e5f9a2b70c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add estate_id + full_name, backfill from users, then set NOT NULL."""
    op.add_column(
        "visitorlog",
        sa.Column("estate_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="core",
    )

    # Backfill each visitor log with the estate of the visited resident.
    op.execute(
        """
        UPDATE core.visitorlog AS vl
        SET estate_id = u.estate_id
        FROM core.users AS u
        WHERE vl.user_id = u.id
          AND vl.estate_id IS NULL
        """
    )

    op.alter_column(
        "visitorlog",
        "estate_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        schema="core",
    )
    op.create_foreign_key(
        "fk_visitorlog_estate_id_estates",
        "visitorlog",
        "estates",
        ["estate_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )

    # Denormalize the host resident's full name onto both log tables. The
    # visitor log uses ``resident_fullname`` to avoid confusion with its
    # existing ``visitor_fullname`` column.
    for table, column in (
        ("visitorlog", "resident_fullname"),
        ("residentlog", "full_name"),
    ):
        op.add_column(
            table,
            sa.Column(column, sa.String(), nullable=True),
            schema="core",
        )
        op.execute(
            f"""
            UPDATE core.{table} AS log
            SET {column} = TRIM(u.first_name || ' ' || u.last_name)
            FROM core.users AS u
            WHERE log.user_id = u.id
              AND log.{column} IS NULL
            """
        )
        op.alter_column(
            table,
            column,
            existing_type=sa.String(),
            nullable=False,
            schema="core",
        )


def downgrade() -> None:
    """Drop the resident-name columns and the estate_id FK/column."""
    op.drop_column("residentlog", "full_name", schema="core")
    op.drop_column("visitorlog", "resident_fullname", schema="core")
    op.drop_constraint(
        "fk_visitorlog_estate_id_estates",
        "visitorlog",
        schema="core",
        type_="foreignkey",
    )
    op.drop_column("visitorlog", "estate_id", schema="core")
