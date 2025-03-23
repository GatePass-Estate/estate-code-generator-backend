"""Initial Migrations

Revision ID: 3cb36234d524
Revises:
Create Date: 2025-03-22 12:44:03.816315

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "3cb36234d524"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


relation = postgresql.ENUM(
    "FAMILY",
    "SPOUSE",
    "FRIEND",
    "TECHNICIAN",
    "TAXI",
    "DELIVERY",
    name="relation",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    # Create schema first
    op.execute("CREATE SCHEMA IF NOT EXISTS core")

    # Create ENUM types first
    relation.create(op.get_bind(), checkfirst=True)

    # Create the visitorlog table
    op.create_table(
        "visitorlog",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("user_id", sa.UUID, nullable=False, unique=False),
        sa.Column("visitor_fullname", sa.String, nullable=False),
        sa.Column("relationship_with_resident", relation, nullable=False),
        sa.Column("hashed_code", sa.String, nullable=False),
        sa.Column("security_id", sa.UUID, nullable=False),
        sa.Column(
            "visit_time",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_visitorlog_id"),
        table_name="visitorlog",
        columns=["id"],
        unique=True,
        schema="core",
    )

    # Create the accesscode table
    op.create_table(
        "accesscode",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("user_id", sa.UUID, nullable=False),
        sa.Column("estate_id", sa.UUID, nullable=False),
        sa.Column("hashed_code", sa.String, nullable=False),
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_accesscode_id"),
        table_name="accesscode",
        columns=["id"],
        unique=True,
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop the accesscode table
    op.drop_index(
        op.f("ix_accesscode_id"), table_name="accesscode", schema="core"
    )
    op.drop_table("accesscode", schema="core")

    # Drop the visitorlog table
    op.drop_index(
        op.f("ix_visitorlog_id"),
        table_name="visitorlog",
        schema="core",
    )
    op.drop_table("visitorlog", schema="core")

    # Drop ENUM types
    relation.drop(op.get_bind(), checkfirst=True)

    # Drop schema last
    op.execute("DROP SCHEMA IF EXISTS core CASCADE")
