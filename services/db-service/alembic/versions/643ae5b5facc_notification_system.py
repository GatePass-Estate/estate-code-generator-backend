"""notification system

Revision ID: 643ae5b5facc
Revises: 85957ce6ec4a
Create Date: 2026-07-04 15:24:22.116227

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "643ae5b5facc"
down_revision: Union[str, None] = "85957ce6ec4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


notificationtype = postgresql.ENUM(
    "GUEST_CODE_USED",
    "RESIDENT_CODE_USED",
    "BROADCAST_RECEIVED",
    "INCIDENT_REPORT_FILED",
    "EDIT_REQUEST_PENDING",
    "EDIT_REQUEST_REVIEWED",
    "LOGIN_NEW_DEVICE",
    "SESSION_REVOKED",
    "PASSWORD_CHANGED",
    "TWO_FA_ENABLED",
    "TWO_FA_DISABLED",
    "TWO_FA_RECOVERY_USED",
    "ROLE_PROMOTED",
    "ROLE_DEMOTED",
    "HOUSEHOLD_TRANSFERRED",
    "FORGOT_PASSWORD",
    "EMAIL_VERIFICATION",
    "WELCOME",
    "PASSWORD_RESET_CONFIRMED",
    "ACCOUNT_CLOSED",
    name="notificationtype",
    schema="core",
    create_type=False,
)

deviceplatform = postgresql.ENUM(
    "IOS",
    "ANDROID",
    name="deviceplatform",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Add notifications, device_tokens, and notification_preferences tables."""
    notificationtype.create(op.get_bind(), checkfirst=True)
    deviceplatform.create(op.get_bind(), checkfirst=True)

    # --- notifications table ---
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id", sa.UUID, sa.ForeignKey("core.users.id"), nullable=False
        ),
        sa.Column("type", notificationtype, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "is_read",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
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
        "ix_core_notifications_id",
        "notifications",
        ["id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "ix_core_notifications_user_unread",
        "notifications",
        ["user_id", "is_read", "created_at"],
        schema="core",
        postgresql_ops={"created_at": "DESC"},
    )

    # --- device_tokens table ---
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id", sa.UUID, sa.ForeignKey("core.users.id"), nullable=False
        ),
        sa.Column(
            "session_id",
            sa.UUID,
            sa.ForeignKey("core.sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token", sa.String, nullable=False, unique=True),
        sa.Column("platform", deviceplatform, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean,
            server_default=sa.text("true"),
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
        "ix_core_device_tokens_id",
        "device_tokens",
        ["id"],
        unique=True,
        schema="core",
    )

    # --- notification_preferences table ---
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id", sa.UUID, sa.ForeignKey("core.users.id"), nullable=False
        ),
        sa.Column("notification_type", notificationtype, nullable=False),
        sa.Column(
            "push_enabled",
            sa.Boolean,
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "email_enabled",
            sa.Boolean,
            server_default=sa.text("true"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "notification_type",
            name="uq_notification_preferences_user_type",
        ),
        schema="core",
    )
    op.create_index(
        "ix_core_notification_preferences_id",
        "notification_preferences",
        ["id"],
        unique=True,
        schema="core",
    )


def downgrade() -> None:
    """Drop notifications, device_tokens, and notification_preferences tables."""
    op.drop_index(
        "ix_core_notification_preferences_id",
        table_name="notification_preferences",
        schema="core",
    )
    op.drop_table("notification_preferences", schema="core")

    op.drop_index(
        "ix_core_device_tokens_id",
        table_name="device_tokens",
        schema="core",
    )
    op.drop_table("device_tokens", schema="core")

    op.drop_index(
        "ix_core_notifications_user_unread",
        table_name="notifications",
        schema="core",
    )
    op.drop_index(
        "ix_core_notifications_id",
        table_name="notifications",
        schema="core",
    )
    op.drop_table("notifications", schema="core")

    deviceplatform.drop(op.get_bind(), checkfirst=True)
    notificationtype.drop(op.get_bind(), checkfirst=True)
