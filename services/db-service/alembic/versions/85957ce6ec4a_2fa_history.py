"""2fa history

Revision ID: 85957ce6ec4a
Revises: b1814a9db371
Create Date: 2026-06-29 21:01:29.525599

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "85957ce6ec4a"
down_revision: Union[str, None] = "b1814a9db371"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_2fa_verified_at to core.users."""
    op.add_column(
        "users",
        sa.Column(
            "last_2fa_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="core",
    )


def downgrade() -> None:
    """Remove last_2fa_verified_at from core.users."""
    op.drop_column("users", "last_2fa_verified_at", schema="core")
