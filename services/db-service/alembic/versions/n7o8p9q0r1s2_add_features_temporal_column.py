"""Add features_temporal JSONB column to logfeatureengineering."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n7o8p9q0r1s2"
down_revision: Union[str, None] = "m6n7o8p9q0r1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "logfeatureengineering",
        sa.Column(
            "features_temporal",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column(
        "logfeatureengineering",
        "features_temporal",
        schema="core",
    )
