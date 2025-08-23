"""add_gender_to_users

Revision ID: 25b7ecb91ef8
Revises: 191f20d87a74
Create Date: 2025-08-16 14:16:07.948444

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "25b7ecb91ef8"
down_revision: Union[str, None] = "191f20d87a74"
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

    # Add gender column to users and guests table
    op.add_column(
        "users",
        sa.Column(
            "gender",
            gender,
            nullable=False,
        ),
        schema="core",
    )

    op.add_column(
        "guests",
        sa.Column(
            "gender",
            gender,
            nullable=False,
        ),
        schema="core",
    )

    # Add additional fields to estates table
    op.add_column(
        "estates",
        sa.Column("lga", sa.String(), nullable=True),
        schema="core",
    )

    op.add_column(
        "estates",
        sa.Column("state", sa.String(), nullable=True),
        schema="core",
    )

    op.add_column(
        "estates",
        sa.Column("country", sa.String(), nullable=True),
        schema="core",
    )

    op.add_column(
        "estates",
        sa.Column("postal_code", sa.String(), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Remove added estate columns
    op.drop_column("estates", "postal_code", schema="core")
    op.drop_column("estates", "country", schema="core")
    op.drop_column("estates", "state", schema="core")
    op.drop_column("estates", "lga", schema="core")

    # Remove gender column from users table
    op.drop_column("guests", "gender", schema="core")
    op.drop_column("users", "gender", schema="core")
