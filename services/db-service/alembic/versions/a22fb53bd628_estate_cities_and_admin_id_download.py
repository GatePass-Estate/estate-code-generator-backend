"""estate cities and admin id download

Revision ID: a22fb53bd628
Revises: df451fe4002d
Create Date: 2026-11-06 17:34:28.686699

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a22fb53bd628"
down_revision: Union[str, None] = "df451fe4002d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add city column (nullable first to backfill)
    op.add_column(
        "estates",
        sa.Column("city", sa.String(), nullable=True),
        schema="core",
    )

    # Backfill existing estates with "City" as default
    op.execute("UPDATE core.estates SET city = 'City' WHERE city IS NULL")

    # Make non-nullable
    op.alter_column("estates", "city", nullable=False, schema="core")


def downgrade() -> None:
    op.drop_column("estates", "city", schema="core")
