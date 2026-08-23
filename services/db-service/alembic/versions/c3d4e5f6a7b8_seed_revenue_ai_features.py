"""seed revenue ai features

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-11 08:02:00.000000

Seeds a minimal core.ai_feature set for revenue Phase 1 testing.
Expand to the full AI feature list once tests pass.
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FEATURE_KEYS = ("visitor_resident_anomaly_detection",)


def upgrade() -> None:
    """Insert minimal ai_feature seed rows."""
    ai_rows = [
        {
            "id": uuid.uuid4(),
            "feature_key": "visitor_resident_anomaly_detection",
            "name": "Visitor/Resident Anomaly Detection",
            "description": None,
            "is_free": False,
            "is_active": True,
            "is_deleted": False,
        },
    ]
    op.bulk_insert(
        sa.table(
            "ai_feature",
            sa.column("id", sa.UUID),
            sa.column("feature_key", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("is_free", sa.Boolean),
            sa.column("is_active", sa.Boolean),
            sa.column("is_deleted", sa.Boolean),
            schema="core",
        ),
        ai_rows,
    )


def downgrade() -> None:
    """Remove seeded ai_feature rows."""
    keys_sql = ", ".join(f"'{key}'" for key in _FEATURE_KEYS)
    op.execute(
        f"DELETE FROM core.ai_feature WHERE feature_key IN ({keys_sql})"
    )
