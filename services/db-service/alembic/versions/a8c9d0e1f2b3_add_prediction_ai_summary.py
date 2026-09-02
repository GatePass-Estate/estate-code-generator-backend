"""Add prediction-result AI summary cache column.

Revision ID: a8c9d0e1f2b3
Revises: f6a7b8c9d0e1
Create Date: 2026-08-30 20:30:00.000000

Adds nullable ``ai_summary`` JSONB on ``core.predictionresult``
(``{"tier1": ..., "tier2": ...}``). Catalog keys are seeded by
``services/ai_service/scripts/seed_anomaly_case_summary_entitlements.py``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8c9d0e1f2b3"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable ``ai_summary`` JSONB on predictionresult."""
    op.add_column(
        "predictionresult",
        sa.Column("ai_summary", postgresql.JSONB(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    """Drop ``ai_summary`` from predictionresult."""
    op.drop_column("predictionresult", "ai_summary", schema="core")
