"""household uniqueness

Revision ID: e7162dc65493
Revises: q0r1s2t3u4v5
Create Date: 2026-09-28 12:23:38.662836

Deduplicate existing household names within the same estate (appending
" (2)", " (3)" etc. to later rows ordered by created_at), then add a
unique constraint on (estate_id, name). NULL names are exempt —
PostgreSQL treats each NULL as distinct.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e7162dc65493"
down_revision: Union[str, None] = "q0r1s2t3u4v5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deduplicate existing names, then enforce uniqueness per estate."""
    # Rename duplicate names within the same estate. The oldest row
    # (by created_at) keeps its original name; later duplicates get
    # " (2)", " (3)" etc. appended. Rows with name IS NULL are untouched.
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY estate_id, name
                       ORDER BY created_at
                   ) AS rn
            FROM core.household
            WHERE name IS NOT NULL
        )
        UPDATE core.household h
        SET name = h.name || ' (' || r.rn::text || ')'
        FROM ranked r
        WHERE h.id = r.id
          AND r.rn > 1
    """)
    op.create_unique_constraint(
        "uq_household_estate_name",
        "household",
        ["estate_id", "name"],
        schema="core",
    )


def downgrade() -> None:
    """Drop the unique constraint (renamed rows are not un-renamed)."""
    op.drop_constraint(
        "uq_household_estate_name",
        "household",
        schema="core",
        type_="unique",
    )
