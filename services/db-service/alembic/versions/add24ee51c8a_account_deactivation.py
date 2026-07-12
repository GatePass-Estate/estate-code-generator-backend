"""Account deactivation: add deactivated_by/at to users and estates,
add is_active to estates, add can_deactivate_user permission.

Revision ID: add24ee51c8a
Revises: 6ce3f93d3c37
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add24ee51c8a"
down_revision: Union[str, None] = "6ce3f93d3c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Roles that are allowed to deactivate users.
_DEACTIVATE_ROLES = ("ROOT", "PRIMARY_ADMIN", "ADMIN")


def upgrade() -> None:
    # ── Users: track who force-closed the account and when ──────────
    op.add_column(
        "users",
        sa.Column(
            "deactivated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="core",
    )
    op.create_foreign_key(
        "fk_users_deactivated_by",
        "users",
        "users",
        ["deactivated_by"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )
    op.add_column(
        "users",
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="core",
    )

    # ── Estates: reversible deactivation ────────────────────────────
    op.add_column(
        "estates",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "estates",
        sa.Column(
            "deactivated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="core",
    )
    op.create_foreign_key(
        "fk_estates_deactivated_by",
        "estates",
        "users",
        ["deactivated_by"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )
    op.add_column(
        "estates",
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="core",
    )

    # ── Role permission: can_deactivate_user flag ────────────────────
    op.add_column(
        "role_permission",
        sa.Column(
            "can_deactivate_user",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="core",
    )
    for role in _DEACTIVATE_ROLES:
        op.execute(
            sa.text(
                "UPDATE core.role_permission"
                " SET can_deactivate_user = true"
                f" WHERE role_name = '{role}'::core.userrole"
            )
        )

    # ── New notification enum values ─────────────────────────────────
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'ACCOUNT_DEACTIVATED'"
    )
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'ACCOUNT_DEACTIVATION_SCHEDULED'"
    )
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'ESTATE_DEACTIVATED'"
    )
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'ESTATE_DEACTIVATION_SCHEDULED'"
    )
    op.execute(
        "ALTER TYPE core.notificationtype"
        " ADD VALUE IF NOT EXISTS 'ESTATE_REACTIVATED'"
    )


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values —
    # the five ACCOUNT_*/ESTATE_* types remain after downgrade.

    op.drop_column("role_permission", "can_deactivate_user", schema="core")

    op.drop_constraint(
        "fk_estates_deactivated_by",
        "estates",
        type_="foreignkey",
        schema="core",
    )
    op.drop_column("estates", "deactivated_at", schema="core")
    op.drop_column("estates", "deactivated_by", schema="core")
    op.drop_column("estates", "is_active", schema="core")

    op.drop_constraint(
        "fk_users_deactivated_by",
        "users",
        type_="foreignkey",
        schema="core",
    )
    op.drop_column("users", "deactivated_at", schema="core")
    op.drop_column("users", "deactivated_by", schema="core")
