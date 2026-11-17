"""add payment charge retry

Revision ID: e75928bd9609
Revises: c8d4e2a91b70
Create Date: 2026-11-16 20:56:45.603227

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e75928bd9609"
down_revision: Union[str, None] = "c8d4e2a91b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payment_charge_retry",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "estate_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column(
            "target_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("paystack_subscription_code", sa.String(), nullable=False),
        sa.Column("billing_period_key", sa.String(), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency_code", sa.String(), nullable=False, server_default="NGN"
        ),
        sa.Column("authorization_code", sa.String(), nullable=False),
        sa.Column("customer_email", sa.String(), nullable=False),
        sa.Column(
            "status", sa.String(), nullable=False, server_default="pending"
        ),
        sa.Column(
            "attempt_number", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_attempted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_gateway_response", sa.Text(), nullable=True),
        sa.Column("last_provider_reference", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default="false"
        ),
        schema="core",
    )

    op.create_unique_constraint(
        "uq_payment_charge_retry_billing_period_key",
        "payment_charge_retry",
        ["billing_period_key"],
        schema="core",
    )

    op.create_index(
        "ix_payment_charge_retry_status_next_retry",
        "payment_charge_retry",
        ["status", "next_retry_at"],
        schema="core",
    )

    op.create_index(
        "ix_payment_charge_retry_target",
        "payment_charge_retry",
        ["target_type", "target_id", "status"],
        schema="core",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_payment_charge_retry_target",
        table_name="payment_charge_retry",
        schema="core",
    )
    op.drop_index(
        "ix_payment_charge_retry_status_next_retry",
        table_name="payment_charge_retry",
        schema="core",
    )
    op.drop_constraint(
        "uq_payment_charge_retry_billing_period_key",
        "payment_charge_retry",
        schema="core",
    )
    op.drop_table("payment_charge_retry", schema="core")
