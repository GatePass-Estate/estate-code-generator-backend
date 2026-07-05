"""Add document view/download RBAC flags to role_permission.

Revision ID: a7b4e9c12f56
Revises: f3a8c2d91e4b
Create Date: 2026-07-05 12:05:00.000000

Seeds per-role values for the four document permission flags (see user
documents GCS plan §7).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b4e9c12f56"
down_revision: Union[str, None] = "f3a8c2d91e4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOCUMENT_FLAG_COLUMNS = (
    "can_view_other_user_documents",
    "can_view_other_user_documents_in_other_estate",
    "can_download_other_user_documents",
    "can_download_other_user_documents_in_other_estate",
)

# role_name values match core.userrole enum storage (uppercase).
_ROLE_DOCUMENT_FLAGS: dict[str, dict[str, bool]] = {
    "ROOT": {
        "can_view_other_user_documents": True,
        "can_view_other_user_documents_in_other_estate": True,
        "can_download_other_user_documents": True,
        "can_download_other_user_documents_in_other_estate": True,
    },
    "PRIMARY_ADMIN": {
        "can_view_other_user_documents": True,
        "can_view_other_user_documents_in_other_estate": False,
        "can_download_other_user_documents": False,
        "can_download_other_user_documents_in_other_estate": False,
    },
    "ADMIN": {
        "can_view_other_user_documents": True,
        "can_view_other_user_documents_in_other_estate": False,
        "can_download_other_user_documents": False,
        "can_download_other_user_documents_in_other_estate": False,
    },
    "SECURITY": {
        "can_view_other_user_documents": True,
        "can_view_other_user_documents_in_other_estate": False,
        "can_download_other_user_documents": False,
        "can_download_other_user_documents_in_other_estate": False,
    },
    "RESIDENT": {
        "can_view_other_user_documents": False,
        "can_view_other_user_documents_in_other_estate": False,
        "can_download_other_user_documents": False,
        "can_download_other_user_documents_in_other_estate": False,
    },
    "GUEST": {
        "can_view_other_user_documents": False,
        "can_view_other_user_documents_in_other_estate": False,
        "can_download_other_user_documents": False,
        "can_download_other_user_documents_in_other_estate": False,
    },
}


def upgrade() -> None:
    """Add document RBAC columns and seed per-role values."""
    for column in _DOCUMENT_FLAG_COLUMNS:
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

    for role_name, flags in _ROLE_DOCUMENT_FLAGS.items():
        set_clause = ", ".join(
            f"{column} = {str(value).lower()}"
            for column, value in flags.items()
        )
        op.execute(
            sa.text(
                f"UPDATE core.role_permission SET {set_clause} "
                f"WHERE role_name = :role_name"
            ).bindparams(role_name=role_name)
        )


def downgrade() -> None:
    """Remove document RBAC columns from role_permission."""
    for column in reversed(_DOCUMENT_FLAG_COLUMNS):
        op.drop_column("role_permission", column, schema="core")
