"""add estate subscription lock columns

Revision ID: f6a7b8c9d0e1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-28 09:00:00.000000

Adds over_cap_locked and renew_attempt_count to core.estate_subscription
for environments that applied a1b2c3d4e5f6 before those columns were added.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add lock and renewal-attempt columns to estate_subscription."""
    op.add_column(
        "estate_subscription",
        sa.Column(
            "over_cap_locked",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "estate_subscription",
        sa.Column(
            "renew_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        schema="core",
    )


def downgrade() -> None:
    """Remove lock and renewal-attempt columns from estate_subscription."""
    op.drop_column("estate_subscription", "renew_attempt_count", schema="core")
    op.drop_column("estate_subscription", "over_cap_locked", schema="core")
