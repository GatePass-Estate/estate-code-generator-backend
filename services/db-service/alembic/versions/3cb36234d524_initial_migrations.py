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
    "PARTNER",
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
    userrole.create(op.get_bind(), checkfirst=True)
    relation.create(op.get_bind(), checkfirst=True)

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
        "ix_core_estates_id", "estates", ["id"], unique=True, schema="core"
    )

    # --- users table ---
    op.create_table(
        "users",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("first_name", sa.String, nullable=False),
        sa.Column("last_name", sa.String, nullable=False),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("phone_number", sa.String, nullable=True),
        sa.Column("password", sa.String, nullable=False),
        sa.Column(
            "estate_id",
            sa.UUID,
            sa.ForeignKey("core.estates.id"),
            nullable=True,
        ),
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
        "ix_core_users_id", "users", ["id"], unique=True, schema="core"
    )

    # Add FK constraint for estates.primary_admin_id → users.id
    op.create_foreign_key(
        "fk_estates_primary_admin_id",
        source_table="estates",
        referent_table="users",
        local_cols=["primary_admin_id"],
        remote_cols=["id"],
        source_schema="core",
        referent_schema="core",
    )

    # --- role_permission table ---
    op.create_table(
        "role_permission",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("role_name", userrole, nullable=False, unique=True),
        sa.Column("can_register_estates", sa.Boolean, default=False),
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
        sa.Column(
            "estate_id",
            sa.UUID,
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.UUID, sa.ForeignKey("core.users.id"), nullable=False
        ),
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
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # --- household table ---
    op.create_table(
        "household",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "estate_id",
            sa.UUID,
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column(
            "primary_resident_id",
            sa.UUID,
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
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
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # --- resident_departure_log table ---
    op.create_table(
        "resident_departure_log",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id", sa.UUID, sa.ForeignKey("core.users.id"), nullable=False
        ),
        sa.Column(
            "estate_id",
            sa.UUID,
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
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
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=True,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )

    # Create the visitorlog table
    op.create_table(
        "visitorlog",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id",
            sa.UUID,
            # sa.ForeignKey("core.users.id"),
            nullable=False,
            unique=False,
        ),
        sa.Column("visitor_fullname", sa.String, nullable=False),
        sa.Column("relationship_with_resident", relation, nullable=False),
        sa.Column("hashed_code", sa.String, nullable=False),
        sa.Column(
            "security_id",
            sa.UUID,
            # sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
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
        "ix_visitorlog_id",
        table_name="visitorlog",
        columns=["id"],
        unique=True,
        schema="core",
    )

    # Create the accesscode table
    op.create_table(
        "accesscode",
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column(
            "user_id",
            sa.UUID,
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column(
            "estate_id",
            sa.UUID,
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
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
        "ix_accesscode_id",
        table_name="accesscode",
        columns=["id"],
        unique=True,
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_core_accesscode_id", table_name="accesscode", schema="core"
    )
    op.drop_table("accesscode", schema="core")
    op.drop_index(
        "ix_core_visitorlog_id", table_name="visitorlog", schema="core"
    )
    op.drop_table("visitorlog", schema="core")
    op.drop_table("resident_departure_log", schema="core")
    op.drop_table("household", schema="core")
    op.drop_table("admin_management", schema="core")
    op.drop_index(
        "ix_core_role_permission_role_name",
        table_name="role_permission",
        schema="core",
    )
    op.drop_table("role_permission", schema="core")

    # Drop the circular FK first
    op.drop_constraint(
        "fk_estates_primary_admin_id",
        table_name="estates",
        schema="core",
        type_="foreignkey",
    )

    op.drop_index("ix_core_users_id", table_name="users", schema="core")
    op.drop_table("users", schema="core")

    op.drop_index("ix_core_estates_id", table_name="estates", schema="core")
    op.drop_table("estates", schema="core")

    userrole.drop(op.get_bind(), checkfirst=True)
    relation.drop(op.get_bind(), checkfirst=True)

    # Drop schema last
    op.execute("DROP SCHEMA IF EXISTS core CASCADE")
