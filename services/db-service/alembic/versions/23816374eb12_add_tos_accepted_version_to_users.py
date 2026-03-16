"""add_tos_accepted_version_to_users

Revision ID: 23816374eb12
Revises: c711e5964ad3
Create Date: 2026-03-13 12:55:49.597339

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "23816374eb12"
down_revision: Union[str, None] = "c711e5964ad3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("tos_accepted_version", sa.String(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "tos_accepted_version", schema="core")
