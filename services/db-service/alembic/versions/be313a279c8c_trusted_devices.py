"""trusted devices

Revision ID: be313a279c8c
Revises: 996c1cb53302
Create Date: 2026-11-13 14:08:22.317647

Server-issued device tokens replace the IP-based device familiarity
check for 2FA skip and new-device notifications.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "be313a279c8c"
down_revision: Union[str, None] = "996c1cb53302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ``core.trusted_devices`` and add FK on ``core.sessions``."""

    # -- 1. trusted_devices table ------------------------------------------
    op.create_table(
        "trusted_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("device_label", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_hash", name="uq_trusted_devices_token_hash"
        ),
        schema="core",
    )

    op.create_index(
        "ix_trusted_devices_id",
        "trusted_devices",
        ["id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "ix_trusted_devices_user_id_token_hash",
        "trusted_devices",
        ["user_id", "token_hash"],
        schema="core",
    )
    op.create_index(
        "ix_trusted_devices_user_id",
        "trusted_devices",
        ["user_id"],
        schema="core",
    )

    # -- 2. FK on sessions -------------------------------------------------
    op.add_column(
        "sessions",
        sa.Column(
            "trusted_device_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="core",
    )
    op.create_foreign_key(
        "fk_sessions_trusted_device_id",
        "sessions",
        "trusted_devices",
        ["trusted_device_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop FK on sessions, then drop trusted_devices."""
    op.drop_constraint(
        "fk_sessions_trusted_device_id",
        "sessions",
        type_="foreignkey",
        schema="core",
    )
    op.drop_column("sessions", "trusted_device_id", schema="core")

    op.drop_index(
        "ix_trusted_devices_user_id",
        table_name="trusted_devices",
        schema="core",
    )
    op.drop_index(
        "ix_trusted_devices_user_id_token_hash",
        table_name="trusted_devices",
        schema="core",
    )
    op.drop_index(
        "ix_trusted_devices_id",
        table_name="trusted_devices",
        schema="core",
    )
    op.drop_table("trusted_devices", schema="core")
