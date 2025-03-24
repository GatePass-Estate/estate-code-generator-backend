"""user profile tables

Revision ID: 33c86d2d7a67
Revises: 3cb36234d524
Create Date: 2025-03-24 12:29:22.757617

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = "33c86d2d7a67"
down_revision: Union[str, None] = "3cb36234d524"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

userrole = postgresql.ENUM(
    "ROOT",
    "PRIMARY_ADMIN",
    "ADMIN",
    "RESIDENT",
    "SECURITY",
    name="userrole",
    schema="core",
    create_type=False,
)

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

    # Create ENUM types first
    userrole.create(op.get_bind(), checkfirst=True)
    relation.create(op.get_bind(), checkfirst=True)

    # --- users table ---
    op.create_table(
        "users",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("first_name", sa.String, nullable=False),
        sa.Column("last_name", sa.String, nullable=False),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("phone_number", sa.String, nullable=True),
        sa.Column("password", sa.String, nullable=False),
        sa.Column("estate_id", sa.UUID, nullable=True),
        sa.Column("role", userrole, nullable=False),
        sa.Column("status", sa.Boolean, nullable=False, server_default="true"),
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
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_users_id", "users", ["id"], unique=True, schema="core"
    )

    # --- estate table ---
    op.create_table(
        "estates",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("location", sa.Text, nullable=False),
        sa.Column("primary_admin_id", sa.UUID, nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_estates_id", "estates", ["id"], unique=True, schema="core"
    )

    # --- role_permission table ---
    op.create_table(
        "role_permission",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("role_name", userrole, nullable=False, unique=True),
        sa.Column("can_register_admin", sa.Boolean, default=False),
        sa.Column("can_register_users", sa.Boolean, default=False),
        sa.Column("can_set_household_limits", sa.Boolean, default=False),
        sa.Column("can_generate_code", sa.Boolean, default=False),
        sa.Column("can_validate_code", sa.Boolean, default=False),
        sa.Column("can_remove_admin", sa.Boolean, default=False),
        sa.Column("can_transfer_admin", sa.Boolean, default=False),
        sa.Column("can_add_household_member", sa.Boolean, default=False),
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
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_role_permission_role_name",
        "role_permission",
        ["role_name"],
        unique=True,
        schema="core",
    )

    # --- admin_management table ---
    op.create_table(
        "admin_management",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("estate_id", sa.UUID, nullable=False),
        sa.Column("user_id", sa.UUID, nullable=False),
        sa.Column("is_primary", sa.Boolean, default=False),
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
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # --- household table ---
    op.create_table(
        "household",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("estate_id", sa.UUID, nullable=False),
        sa.Column("primary_resident_id", sa.UUID, nullable=False),
        sa.Column(
            "max_members", sa.Integer, nullable=False, server_default="10"
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
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # --- resident_departure_log table ---
    op.create_table(
        "resident_departure_log",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("user_id", sa.UUID, nullable=False),
        sa.Column("estate_id", sa.UUID, nullable=False),
        sa.Column(
            "departure_time",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column("reason", sa.Text, nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("resident_departure_log", schema="core")
    op.drop_table("household", schema="core")
    op.drop_table("admin_management", schema="core")
    op.drop_index(
        "ix_core_role_permission_role_name",
        table_name="role_permission",
        schema="core",
    )
    op.drop_table("role_permission", schema="core")
    op.drop_index("ix_core_estates_id", table_name="estates", schema="core")
    op.drop_table("estate", schema="core")
    op.drop_index("ix_core_users_id", table_name="users", schema="core")
    op.drop_table("users", schema="core")

    userrole.drop(op.get_bind(), checkfirst=True)
    relation.drop(op.get_bind(), checkfirst=True)
