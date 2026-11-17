"""add estate types

Revision ID: ad30c8201e86
Revises: 2909bc1ea4d9
Create Date: 2026-06-10 20:36:16.405095

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ad30c8201e86"
down_revision: Union[str, None] = "2909bc1ea4d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

estatetype = postgresql.ENUM(
    "housing",
    "corporate",
    name="estatetype",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    estatetype.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "estates",
        sa.Column("estate_type", estatetype, nullable=True),
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("estates", "estate_type", schema="core")
    estatetype.drop(op.get_bind(), checkfirst=True)
