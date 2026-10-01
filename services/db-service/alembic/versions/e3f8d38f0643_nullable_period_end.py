"""nullable period_end on estate_subscription

Revision ID: e3f8d38f0643
Revises: a91f0ff33ba6
Create Date: 2026-10-01 23:18:47.802299

Make period_end nullable to support access-tier subscriptions that have
no billing cycle (perpetual). period_start remains non-nullable and is set
to the provisioning timestamp so we keep an "on access since [date]" record.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f8d38f0643"
down_revision: Union[str, None] = "a91f0ff33ba6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "estate_subscription",
        "period_end",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        schema="core",
    )


def downgrade() -> None:
    # Re-applying NOT NULL requires all rows to have a non-null value first.
    # Set a placeholder for any NULLs (access subscriptions) before the
    # constraint is reinstated.
    op.execute(
        "UPDATE core.estate_subscription "
        "SET period_end = NOW() + INTERVAL '100 years' "
        "WHERE period_end IS NULL"
    )
    op.alter_column(
        "estate_subscription",
        "period_end",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        schema="core",
    )
