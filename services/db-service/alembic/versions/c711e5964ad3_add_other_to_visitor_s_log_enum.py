"""add OTHER to visitor's log enum

Revision ID: c711e5964ad3
Revises: b033dd6f9794
Create Date: 2026-03-01 08:41:57.311365

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c711e5964ad3"
down_revision: Union[str, None] = "b033dd6f9794"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE core.relation ADD VALUE IF NOT EXISTS 'OTHER'")


def downgrade() -> None:
    """Downgrade schema.

    Note: PostgreSQL does not support removing values from enum types.
    Reverting would require recreating the type and all dependent columns.
    """
    pass
