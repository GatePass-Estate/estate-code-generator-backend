"""pending covered users

Revision ID: a91f0ff33ba6
Revises: 376ce65fe157
Create Date: 2026-09-30 01:13:28.695853

Add pending_covered_users to estate_subscription to support scheduled seat
reductions that take effect on the next billing cycle.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a91f0ff33ba6"
down_revision: Union[str, None] = "376ce65fe157"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "estate_subscription",
        sa.Column("pending_covered_users", sa.Integer(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column(
        "estate_subscription", "pending_covered_users", schema="core"
    )
