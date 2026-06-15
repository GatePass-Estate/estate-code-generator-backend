"""multiple email accounts

Revision ID: 2909bc1ea4d9
Revises: c17962ae653d
Create Date: 2026-06-10 18:14:16.498505

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2909bc1ea4d9"
down_revision: Union[str, None] = "c17962ae653d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Multi-estate email: replace global unique on email with partial unique indexes
    op.drop_constraint(
        "users_email_key", "users", schema="core", type_="unique"
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_users_active_email_estate
        ON core.users (email, estate_id)
        WHERE status = TRUE AND is_deleted = FALSE
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_users_active_email_no_estate
        ON core.users (email)
        WHERE estate_id IS NULL AND status = TRUE AND is_deleted = FALSE
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS core.uq_users_active_email_estate")
    op.execute("DROP INDEX IF EXISTS core.uq_users_active_email_no_estate")
    op.create_unique_constraint(
        "users_email_key", "users", ["email"], schema="core"
    )
