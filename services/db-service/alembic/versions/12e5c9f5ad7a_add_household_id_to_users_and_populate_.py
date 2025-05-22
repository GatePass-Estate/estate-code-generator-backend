"""Add household_id to users and populate role permissions

Revision ID: 12e5c9f5ad7a
Revises: 3cb36234d524
Create Date: 2025-05-12 14:17:14.013220

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from uuid import uuid4
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision: str = "12e5c9f5ad7a"
down_revision: Union[str, None] = "3cb36234d524"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define ENUM again to match existing PostgreSQL ENUM
userrole_enum = sa.Enum(
    "ROOT",
    "PRIMARY_ADMIN",
    "ADMIN",
    "RESIDENT",
    "SECURITY",
    "GUEST",
    name="userrole",
    schema="core",
    native_enum=True,
)

now = datetime.now(timezone.utc)


def upgrade():
    # Add household_id to users
    op.add_column(
        "users",
        sa.Column(
            "household_id",
            sa.UUID,
            sa.ForeignKey("core.household.id"),
            nullable=True,
        ),
        schema="core",
    )

    # Insert role permissions
    roles = [
        {
            "id": uuid4(),
            "role_name": "ROOT",
            "can_register_estates": True,
            "can_register_admin": True,
            "can_register_users": True,
            "can_set_household_limits": True,
            "can_generate_code": True,
            "can_validate_code": True,
            "can_remove_admin": True,
            "can_transfer_admin": True,
            "can_add_household_member": True,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        },
        {
            "id": uuid4(),
            "role_name": "PRIMARY_ADMIN",
            "can_register_estates": False,
            "can_register_admin": True,
            "can_register_users": True,
            "can_set_household_limits": True,
            "can_generate_code": True,
            "can_validate_code": True,
            "can_remove_admin": True,
            "can_transfer_admin": True,
            "can_add_household_member": True,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        },
        {
            "id": uuid4(),
            "role_name": "ADMIN",
            "can_register_estates": False,
            "can_register_admin": False,
            "can_register_users": True,
            "can_set_household_limits": True,
            "can_generate_code": True,
            "can_validate_code": True,
            "can_remove_admin": False,
            "can_transfer_admin": False,
            "can_add_household_member": True,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        },
        {
            "id": uuid4(),
            "role_name": "RESIDENT",
            "can_register_estates": False,
            "can_register_admin": False,
            "can_register_users": False,
            "can_set_household_limits": False,
            "can_generate_code": True,
            "can_validate_code": False,
            "can_remove_admin": False,
            "can_transfer_admin": False,
            "can_add_household_member": False,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        },
        {
            "id": uuid4(),
            "role_name": "SECURITY",
            "can_register_estates": False,
            "can_register_admin": False,
            "can_register_users": False,
            "can_set_household_limits": False,
            "can_generate_code": False,
            "can_validate_code": True,
            "can_remove_admin": False,
            "can_transfer_admin": False,
            "can_add_household_member": False,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        },
        {
            "id": uuid4(),
            "role_name": "GUEST",
            "can_register_estates": False,
            "can_register_admin": False,
            "can_register_users": False,
            "can_set_household_limits": False,
            "can_generate_code": False,
            "can_validate_code": False,
            "can_remove_admin": False,
            "can_transfer_admin": False,
            "can_add_household_member": False,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        },
    ]

    # Define a SQLAlchemy table (structure must match your actual table)
    role_permission_table = sa.Table(
        "role_permission",
        sa.MetaData(),
        sa.Column("id", sa.UUID, nullable=False),
        sa.Column("role_name", userrole_enum, nullable=False),
        sa.Column("can_register_estates", sa.Boolean),
        sa.Column("can_register_admin", sa.Boolean),
        sa.Column("can_register_users", sa.Boolean),
        sa.Column("can_set_household_limits", sa.Boolean),
        sa.Column("can_generate_code", sa.Boolean),
        sa.Column("can_validate_code", sa.Boolean),
        sa.Column("can_remove_admin", sa.Boolean),
        sa.Column("can_transfer_admin", sa.Boolean),
        sa.Column("can_add_household_member", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean),
        schema="core",
    )

    op.bulk_insert(role_permission_table, roles)


def downgrade():
    op.drop_column("users", "household_id", schema="core")

    # Optional: delete the inserted permissions
    op.execute(
        "DELETE FROM core.role_permission WHERE role_name IN ('ROOT',"
        " 'PRIMARY_ADMIN', 'ADMIN', 'RESIDENT', 'SECURITY', 'GUEST')"
    )
