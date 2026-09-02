"""Add SPATIAL_ANOMALY_DETECTED to notificationtype.

Revision ID: e8b4c2d91a70
Revises: f6a7b8c9d0e1
Create Date: 2026-08-31 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e8b4c2d91a70"
down_revision: Union[str, None] = "a8c9d0e1f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'SPATIAL_ANOMALY_DETECTED'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values —
    # SPATIAL_ANOMALY_DETECTED will remain in core.notificationtype.
    pass
