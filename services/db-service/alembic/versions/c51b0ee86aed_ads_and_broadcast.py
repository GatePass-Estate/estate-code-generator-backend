"""ads and broadcast

Revision ID: c51b0ee86aed
Revises: add24ee51c8a
Create Date: 2026-07-30 17:58:30.986185

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c51b0ee86aed"
down_revision: Union[str, None] = "add24ee51c8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_broadcast_priority_enum = postgresql.ENUM(
    "LOW",
    "MEDIUM",
    "HIGH",
    name="broadcast_priority",
    schema="core",
    create_type=False,
)

_broadcast_category_enum = postgresql.ENUM(
    "BROADCAST",
    "AD",
    name="broadcast_category",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create broadcast_priority enum
    op.execute(
        "CREATE TYPE core.broadcast_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH')"
    )

    # 2. Replace broadcasts.audience: drop old single-enum column, add TEXT[]
    op.drop_column("broadcasts", "audience", schema="core")
    op.execute("DROP TYPE IF EXISTS core.audience")
    op.add_column(
        "broadcasts",
        sa.Column(
            "audience",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        schema="core",
    )

    # 3. Add priority column (defaults to LOW for any existing rows)
    op.add_column(
        "broadcasts",
        sa.Column(
            "priority",
            _broadcast_priority_enum,
            nullable=False,
            server_default="LOW",
        ),
        schema="core",
    )

    # 4. Add optional custom sender display name
    op.add_column(
        "broadcasts",
        sa.Column("sender_name", sa.String(), nullable=True),
        schema="core",
    )

    # 5. Add BROADCAST_HIGH and BROADCAST_MEDIUM to the notificationtype enum
    op.execute(
        "ALTER TYPE core.notificationtype ADD VALUE IF NOT EXISTS 'BROADCAST_HIGH'"
    )
    op.execute(
        "ALTER TYPE core.notificationtype ADD VALUE IF NOT EXISTS 'BROADCAST_MEDIUM'"
    )

    # 6. Create broadcast_reads table
    op.create_table(
        "broadcast_reads",
        sa.Column("broadcast_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
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
        sa.ForeignKeyConstraint(
            ["broadcast_id"], ["core.broadcasts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["core.users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broadcast_id",
            "user_id",
            name="uq_broadcast_reads_broadcast_user",
        ),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_broadcast_reads_broadcast_id"),
        "broadcast_reads",
        ["broadcast_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        op.f("ix_core_broadcast_reads_user_id"),
        "broadcast_reads",
        ["user_id"],
        unique=False,
        schema="core",
    )

    # 7. Add broadcast_category enum and category column to broadcasts
    op.execute(
        "CREATE TYPE core.broadcast_category AS ENUM ('BROADCAST', 'AD')"
    )
    op.add_column(
        "broadcasts",
        sa.Column(
            "category",
            _broadcast_category_enum,
            nullable=False,
            server_default="BROADCAST",
        ),
        schema="core",
    )

    # 8. Add is_dismissed to broadcast_reads
    op.add_column(
        "broadcast_reads",
        sa.Column(
            "is_dismissed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        schema="core",
    )

    # 9. Add can_create_broadcast to role_permission
    op.add_column(
        "role_permission",
        sa.Column(
            "can_create_broadcast",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=True,
        ),
        schema="core",
    )
    # Grant broadcast creation to root, primary_admin, and admin
    op.execute(
        "UPDATE core.role_permission "
        "SET can_create_broadcast = true "
        "WHERE role_name IN ('ROOT', 'PRIMARY_ADMIN', 'ADMIN')"
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop broadcast_reads
    op.drop_index(
        op.f("ix_core_broadcast_reads_user_id"),
        table_name="broadcast_reads",
        schema="core",
    )
    op.drop_index(
        op.f("ix_core_broadcast_reads_broadcast_id"),
        table_name="broadcast_reads",
        schema="core",
    )
    op.drop_table("broadcast_reads", schema="core")

    # Remove added columns from broadcasts
    op.drop_column("broadcasts", "sender_name", schema="core")
    op.drop_column("broadcasts", "priority", schema="core")
    op.drop_column("broadcasts", "audience", schema="core")
    op.execute("DROP TYPE IF EXISTS core.broadcast_priority")

    # Restore original audience enum + column
    op.execute(
        "CREATE TYPE core.audience AS ENUM "
        "('ALL', 'ROOT', 'PRIMARY_ADMIN', 'ADMIN', 'RESIDENT', 'SECURITY', 'GUEST')"
    )
    op.add_column(
        "broadcasts",
        sa.Column(
            "audience",
            postgresql.ENUM(
                "ALL",
                "ROOT",
                "PRIMARY_ADMIN",
                "ADMIN",
                "RESIDENT",
                "SECURITY",
                "GUEST",
                name="audience",
                schema="core",
                create_type=False,
            ),
            nullable=False,
            server_default="ALL",
        ),
        schema="core",
    )
    op.drop_column("role_permission", "can_create_broadcast", schema="core")
    op.drop_column("broadcast_reads", "is_dismissed", schema="core")
    op.drop_column("broadcasts", "category", schema="core")
    op.execute("DROP TYPE IF EXISTS core.broadcast_category")

    # Note: BROADCAST_HIGH and BROADCAST_MEDIUM cannot be removed from
    # the notificationtype enum in PostgreSQL without a full type rebuild.
    # They are simply unused after downgrade.
