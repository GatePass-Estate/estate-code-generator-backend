"""session management and totp

Revision ID: b1814a9db371
Revises: ad30c8201e86
Create Date: 2026-06-20 14:54:09.186858

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1814a9db371"
down_revision: Union[str, None] = "ad30c8201e86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Sessions table
    op.create_table(
        "sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column(
            "last_active_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_2fa_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["core.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_sessions_id"),
        "sessions",
        ["id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "ix_core_sessions_user_id", "sessions", ["user_id"], schema="core"
    )

    # TOTP recovery codes table
    op.create_table(
        "totp_recovery_codes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["core.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_totp_recovery_codes_id"),
        "totp_recovery_codes",
        ["id"],
        unique=True,
        schema="core",
    )

    # TOTP fields on users
    op.add_column(
        "users",
        sa.Column("totp_secret", sa.String(), nullable=True),
        schema="core",
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "totp_enabled", schema="core")
    op.drop_column("users", "totp_secret", schema="core")
    op.drop_index(
        op.f("ix_core_totp_recovery_codes_id"),
        table_name="totp_recovery_codes",
        schema="core",
    )
    op.drop_table("totp_recovery_codes", schema="core")
    op.drop_index(
        "ix_core_sessions_user_id", table_name="sessions", schema="core"
    )
    op.drop_index(
        op.f("ix_core_sessions_id"), table_name="sessions", schema="core"
    )
    op.drop_table("sessions", schema="core")
