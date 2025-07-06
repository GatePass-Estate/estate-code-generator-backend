"""Add Guests, Broadcasts and Requests tables

Revision ID: 7b8ff7bb4794
Revises: 12e5c9f5ad7a
Create Date: 2025-07-06 21:53:32.473124

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = "7b8ff7bb4794"
down_revision: Union[str, None] = "12e5c9f5ad7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


requesttype = postgresql.ENUM(
    "NAME",
    "EMAIL",
    "ADDRESS",
    "VACATE",
    name="requesttype",
    schema="core",
    create_type=False,
)

status = postgresql.ENUM(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="status",
    schema="core",
    create_type=False,
)

audience = postgresql.ENUM(
    "ALL",
    "ROOT",
    "PRIMARY_ADMIN",
    "ADMIN",
    "RESIDENT",
    "SECURITY",
    "GUEST",
    name="audience",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    # Add admin_id to resident departure logs
    op.add_column(
        "resident_departure_log",
        sa.Column(
            "admin_id",
            sa.UUID,
            sa.ForeignKey("core.users.id"),
            nullable=True,
        ),
        schema="core",
    )

    # Create ENUM types first
    requesttype.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)
    audience.create(op.get_bind(), checkfirst=True)

    # Create tables
    op.create_table(
        "guests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "resident_id",
            sa.UUID(),
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column("guest_name", sa.String(), nullable=False),
        sa.Column("guest_phone_number", sa.String(), nullable=True),
        sa.Column("relationship", sa.String(), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_guests_id", "guests", ["id"], unique=True, schema="core"
    )

    op.create_table(
        "requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "resident_id",
            sa.UUID(),
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column(
            "estate_id",
            sa.UUID(),
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column("request_type", requesttype, nullable=False),
        sa.Column("old_value", sa.String(), nullable=False),
        sa.Column("new_value", sa.String(), nullable=True),
        sa.Column("status", status, nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_requests_id", "requests", ["id"], unique=True, schema="core"
    )

    op.create_table(
        "broadcasts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "estate_id",
            sa.UUID(),
            sa.ForeignKey("core.estates.id"),
            nullable=True,
        ),
        sa.Column(
            "sender_id",
            sa.UUID(),
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("audience", audience, nullable=False),
        sa.Column("attachment_url", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_broadcasts_id",
        "broadcasts",
        ["id"],
        unique=True,
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_core_broadcasts_id", table_name="broadcasts", schema="core"
    )
    op.drop_table("broadcasts", schema="core")
    op.drop_index("ix_core_requests_id", table_name="requests", schema="core")
    op.drop_table("requests", schema="core")
    op.drop_index("ix_core_guests_id", table_name="guests", schema="core")
    op.drop_table("guests", schema="core")
    op.drop_column("resident_departure_log", "admin_id", schema="core")
