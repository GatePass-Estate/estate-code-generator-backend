"""checkout idempotency hardening

Revision ID: 996c1cb53302
Revises: a22fb53bd628
Create Date: 2026-11-08 14:22:05.667342

Adds request_hash and expires_at columns to payment_checkout_session.
Replaces the single-column idempotency_key unique constraint with a
composite (initiated_by_user_id, idempotency_key) constraint so keys
are scoped per user.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "996c1cb53302"
down_revision: Union[str, None] = "a22fb53bd628"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add request_hash column
    op.add_column(
        "payment_checkout_session",
        sa.Column("request_hash", sa.String(64), nullable=True),
        schema="core",
    )

    # Add expires_at column only if it doesn't already exist
    # (original migration created it but the model didn't map it).
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'core' "
            "AND table_name = 'payment_checkout_session' "
            "AND column_name = 'expires_at'"
        )
    )
    if result.fetchone() is None:
        op.add_column(
            "payment_checkout_session",
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            schema="core",
        )

    # Drop old single-column unique constraint on idempotency_key
    op.drop_constraint(
        "payment_checkout_session_idempotency_key_key",
        "payment_checkout_session",
        schema="core",
        type_="unique",
    )

    # Create composite unique constraint scoped to user
    op.create_unique_constraint(
        "uq_checkout_user_idempotency",
        "payment_checkout_session",
        ["initiated_by_user_id", "idempotency_key"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_checkout_user_idempotency",
        "payment_checkout_session",
        schema="core",
        type_="unique",
    )

    op.create_unique_constraint(
        "payment_checkout_session_idempotency_key_key",
        "payment_checkout_session",
        ["idempotency_key"],
        schema="core",
    )

    op.drop_column("payment_checkout_session", "request_hash", schema="core")
