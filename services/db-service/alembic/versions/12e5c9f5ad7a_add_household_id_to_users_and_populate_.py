"""Add household_id to users and populate role permissions

Revision ID: 12e5c9f5ad7a
Revises: 3cb36234d524
Create Date: 2025-05-12 14:17:14.013220

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from uuid import uuid4

# revision identifiers, used by Alembic.
revision: str = "12e5c9f5ad7a"
down_revision: Union[str, None] = "3cb36234d524"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
        },
        {
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
        },
        {
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
        },
        {
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
        },
        {
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
        },
        {
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
        },
    ]

    stmt = sa.text(
        """
        INSERT INTO core.role_permission (
            id,
            role_name,
            can_register_estates,
            can_register_admin,
            can_register_users,
            can_set_household_limits,
            can_generate_code,
            can_validate_code,
            can_remove_admin,
            can_transfer_admin,
            can_add_household_member,
            created_at,
            updated_at,
            is_deleted
        ) VALUES (
            :id,
            CAST(:role_name AS core.userrole),
            :can_register_estates,
            :can_register_admin,
            :can_register_users,
            :can_set_household_limits,
            :can_generate_code,
            :can_validate_code,
            :can_remove_admin,
            :can_transfer_admin,
            :can_add_household_member,
            NOW(),
            NOW(),
            false
        )
        """
    )

    for role in roles:
        op.execute(
            stmt.bindparams(
                sa.bindparam("id", value=uuid4()),
                sa.bindparam("role_name", value=role["role_name"]),
                sa.bindparam(
                    "can_register_estates", value=role["can_register_estates"]
                ),
                sa.bindparam(
                    "can_register_admin", value=role["can_register_admin"]
                ),
                sa.bindparam(
                    "can_register_users", value=role["can_register_users"]
                ),
                sa.bindparam(
                    "can_set_household_limits",
                    value=role["can_set_household_limits"],
                ),
                sa.bindparam(
                    "can_generate_code", value=role["can_generate_code"]
                ),
                sa.bindparam(
                    "can_validate_code", value=role["can_validate_code"]
                ),
                sa.bindparam(
                    "can_remove_admin", value=role["can_remove_admin"]
                ),
                sa.bindparam(
                    "can_transfer_admin", value=role["can_transfer_admin"]
                ),
                sa.bindparam(
                    "can_add_household_member",
                    value=role["can_add_household_member"],
                ),
            )
        )


def downgrade():
    op.drop_column("users", "household_id", schema="core")

    # Optional: delete the inserted permissions
    op.execute(
        "DELETE FROM core.role_permission WHERE role_name IN ('ROOT',"
        " 'PRIMARY_ADMIN', 'ADMIN', 'RESIDENT', 'SECURITY', 'GUEST')"
    )
