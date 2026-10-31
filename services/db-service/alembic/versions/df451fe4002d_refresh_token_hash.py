"""refresh token hash

Revision ID: df451fe4002d
Revises: ff55f753b8a4
Create Date: 2026-10-31 15:23:14.798106

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "df451fe4002d"
down_revision: Union[str, None] = "ff55f753b8a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add refresh_token_hash column to core.sessions."""
    op.add_column(
        "sessions",
        sa.Column("refresh_token_hash", sa.Text(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    """Remove refresh_token_hash column from core.sessions."""
    op.drop_column("sessions", "refresh_token_hash", schema="core")
