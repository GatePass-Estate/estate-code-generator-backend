"""add id_change to core.requesttype enum

Revision ID: c9d4e81f2a30
Revises: a7b4e9c12f56
Create Date: 2026-07-08 15:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d4e81f2a30"
down_revision: Union[str, None] = "a7b4e9c12f56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ID_CHANGE to the request type enum."""
    op.execute(
        "ALTER TYPE core.requesttype ADD VALUE IF NOT EXISTS 'ID_CHANGE'"
    )


def downgrade() -> None:
    """Enum value removal is not supported; no-op downgrade."""
    pass
