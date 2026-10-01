"""pending tier slug

Revision ID: 376ce65fe157
Revises: 908a9b2d91d1
Create Date: 2026-09-29 15:44:22.932215

Add pending_tier_slug to estate_subscription to support scheduled tier
upgrades and downgrades that take effect on the next billing cycle.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "376ce65fe157"
down_revision: Union[str, None] = "908a9b2d91d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "estate_subscription",
        sa.Column("pending_tier_slug", sa.String(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("estate_subscription", "pending_tier_slug", schema="core")
