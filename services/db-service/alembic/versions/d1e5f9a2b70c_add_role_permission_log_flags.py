"""Add log view RBAC flags to role_permission.

Revision ID: d1e5f9a2b70c
Revises: c9d4e81f2a30
Create Date: 2026-07-09 09:00:00.000000

Seeds per-role values for the two log-view permission flags used by the
resident/visitor access-history endpoints. Root may view any user's logs in
any estate; admin/primary_admin/security may view other users' logs within
their own estate only.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e5f9a2b70c"
down_revision: Union[str, None] = "c9d4e81f2a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOG_FLAG_COLUMNS = (
    "can_view_other_user_logs",
    "can_view_other_user_logs_in_other_estate",
)

# role_name values match core.userrole enum storage (uppercase).
_ROLE_LOG_FLAGS: dict[str, dict[str, bool]] = {
    "ROOT": {
        "can_view_other_user_logs": True,
        "can_view_other_user_logs_in_other_estate": True,
    },
    "PRIMARY_ADMIN": {
        "can_view_other_user_logs": True,
        "can_view_other_user_logs_in_other_estate": False,
    },
    "ADMIN": {
        "can_view_other_user_logs": True,
        "can_view_other_user_logs_in_other_estate": False,
    },
    "SECURITY": {
        "can_view_other_user_logs": True,
        "can_view_other_user_logs_in_other_estate": False,
    },
    "RESIDENT": {
        "can_view_other_user_logs": False,
        "can_view_other_user_logs_in_other_estate": False,
    },
    "GUEST": {
        "can_view_other_user_logs": False,
        "can_view_other_user_logs_in_other_estate": False,
    },
}


def upgrade() -> None:
    """Add log RBAC columns and seed per-role values."""
    for column in _LOG_FLAG_COLUMNS:
        op.add_column(
            "role_permission",
            sa.Column(
                column,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            schema="core",
        )

    for role_name, flags in _ROLE_LOG_FLAGS.items():
        set_clause = ", ".join(
            f"{column} = {str(value).lower()}"
            for column, value in flags.items()
        )
        op.execute(
            sa.text(
                f"UPDATE core.role_permission SET {set_clause} "
                f"WHERE role_name = '{role_name}'::core.userrole"
            )
        )


def downgrade() -> None:
    """Remove log RBAC columns from role_permission."""
    for column in reversed(_LOG_FLAG_COLUMNS):
        op.drop_column("role_permission", column, schema="core")
