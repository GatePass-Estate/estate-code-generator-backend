"""add gender to visitor's log

Revision ID: 191f20d87a74
Revises: 7b8ff7bb4794
Create Date: 2025-07-27 16:55:18.798875

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "191f20d87a74"
down_revision: Union[str, None] = "7b8ff7bb4794"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


gender = postgresql.ENUM(
    "MALE",
    "FEMALE",
    "PREFER_NOT_TO_SAY",
    name="gender",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    gender.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "visitorlog",
        sa.Column(
            "gender",
            gender,
            nullable=False,
        ),
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("visitorlog", "gender", schema="core")

    gender.drop(op.get_bind(), checkfirst=True)
