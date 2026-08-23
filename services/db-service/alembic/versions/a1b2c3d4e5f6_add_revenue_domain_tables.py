"""add revenue domain tables

Revision ID: a1b2c3d4e5f6
Revises: c51b0ee86aed
Create Date: 2026-08-11 08:00:00.000000

Creates revenue catalog, subscription, AI grant, and payment tables only
(no seed data; see chained seed migrations).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c51b0ee86aed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create revenue tables and indexes."""
    # --- service_catalog ---
    op.create_table(
        "service_catalog",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("service_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("limit_type", sa.String(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_key"),
        schema="core",
    )
    op.create_index(
        "ix_core_service_catalog_id",
        "service_catalog",
        ["id"],
        unique=True,
        schema="core",
    )

    # --- ai_feature ---
    op.create_table(
        "ai_feature",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("feature_key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_free", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_key"),
        schema="core",
    )
    op.create_index(
        "ix_core_ai_feature_id",
        "ai_feature",
        ["id"],
        unique=True,
        schema="core",
    )

    # --- feature_unit_price ---
    op.create_table(
        "feature_unit_price",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("country_code", sa.String(), nullable=False),
        sa.Column("currency_code", sa.String(), nullable=False),
        sa.Column("feature_kind", sa.String(), nullable=False),
        sa.Column("service_catalog_id", sa.UUID(), nullable=True),
        sa.Column("ai_feature_id", sa.UUID(), nullable=True),
        sa.Column("feature_unit_price", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["service_catalog_id"],
            ["core.service_catalog.id"],
        ),
        sa.ForeignKeyConstraint(
            ["ai_feature_id"],
            ["core.ai_feature.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_feature_unit_price_id",
        "feature_unit_price",
        ["id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "uq_feature_unit_price_country_service",
        "feature_unit_price",
        ["country_code", "service_catalog_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text(
            "service_catalog_id IS NOT NULL AND is_deleted = false"
        ),
    )
    op.create_index(
        "uq_feature_unit_price_country_ai",
        "feature_unit_price",
        ["country_code", "ai_feature_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text(
            "ai_feature_id IS NOT NULL AND is_deleted = false"
        ),
    )

    # --- subscription_tier ---
    op.create_table(
        "subscription_tier",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "display_order", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "entitlements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "included_ai_features",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "is_custom", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("billing_unit_hint", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        schema="core",
    )
    op.create_index(
        "ix_core_subscription_tier_id",
        "subscription_tier",
        ["id"],
        unique=True,
        schema="core",
    )

    # --- estate_subscription ---
    op.create_table(
        "estate_subscription",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("estate_id", sa.UUID(), nullable=False),
        sa.Column("tier_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "auto_renew", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "covered_users", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "over_cap_locked",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "entitlements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("paystack_subscription_code", sa.String(), nullable=True),
        sa.Column("paystack_customer_code", sa.String(), nullable=True),
        sa.Column(
            "renew_attempt_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "last_renewal_failure_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_renewal_failure_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["estate_id"], ["core.estates.id"]),
        sa.ForeignKeyConstraint(["tier_id"], ["core.subscription_tier.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_estate_subscription_id",
        "estate_subscription",
        ["id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "uq_estate_subscription_active_estate",
        "estate_subscription",
        ["estate_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text(
            "status IN ('active', 'trialing', 'past_due') AND is_deleted = false"
        ),
    )

    # --- estate_ai_feature ---
    op.create_table(
        "estate_ai_feature",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("estate_id", sa.UUID(), nullable=False),
        sa.Column("ai_feature_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("estate_subscription_id", sa.UUID(), nullable=True),
        # checkout_session_id FK added after payment_checkout_session exists
        sa.Column("checkout_session_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_installed", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "status", sa.String(), server_default="active", nullable=False
        ),
        sa.Column(
            "is_free", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "auto_renew", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["estate_id"], ["core.estates.id"]),
        sa.ForeignKeyConstraint(["ai_feature_id"], ["core.ai_feature.id"]),
        sa.ForeignKeyConstraint(
            ["estate_subscription_id"], ["core.estate_subscription.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_estate_ai_feature_id",
        "estate_ai_feature",
        ["id"],
        unique=True,
        schema="core",
    )
    op.create_index(
        "uq_estate_ai_feature_estate_feature",
        "estate_ai_feature",
        ["estate_id", "ai_feature_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("is_deleted = false"),
    )

    # --- payment_checkout_session ---
    op.create_table(
        "payment_checkout_session",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("estate_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("paystack_reference", sa.String(), nullable=True),
        sa.Column(
            "status", sa.String(), server_default="pending", nullable=False
        ),
        sa.Column(
            "pricing_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency_code", sa.String(), nullable=False),
        sa.Column("country_code", sa.String(), nullable=False),
        sa.Column("checkout_kind", sa.String(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("callback_url", sa.String(), nullable=True),
        sa.Column("initiated_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["estate_id"], ["core.estates.id"]),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["core.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("paystack_reference"),
        schema="core",
    )
    op.create_index(
        "ix_core_payment_checkout_session_id",
        "payment_checkout_session",
        ["id"],
        unique=True,
        schema="core",
    )

    # --- payment_event ---
    op.create_table(
        "payment_event",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column(
            "provider", sa.String(), server_default="paystack", nullable=False
        ),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        schema="core",
    )
    op.create_index(
        "ix_core_payment_event_id",
        "payment_event",
        ["id"],
        unique=True,
        schema="core",
    )

    # --- payment_transaction ---
    op.create_table(
        "payment_transaction",
        sa.Column("id", sa.UUID(), nullable=False),
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
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("estate_id", sa.UUID(), nullable=False),
        sa.Column("checkout_session_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency_code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provider_reference", sa.String(), nullable=True),
        sa.Column(
            "raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(["estate_id"], ["core.estates.id"]),
        sa.ForeignKeyConstraint(
            ["checkout_session_id"],
            ["core.payment_checkout_session.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_payment_transaction_id",
        "payment_transaction",
        ["id"],
        unique=True,
        schema="core",
    )

    op.create_foreign_key(
        "fk_estate_ai_feature_checkout_session_id",
        "estate_ai_feature",
        "payment_checkout_session",
        ["checkout_session_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
    )


def downgrade() -> None:
    """Drop revenue tables."""
    op.drop_constraint(
        "fk_estate_ai_feature_checkout_session_id",
        "estate_ai_feature",
        schema="core",
        type_="foreignkey",
    )
    op.drop_table("payment_transaction", schema="core")
    op.drop_table("payment_event", schema="core")
    op.drop_table("estate_ai_feature", schema="core")
    op.drop_table("payment_checkout_session", schema="core")
    op.drop_table("estate_subscription", schema="core")
    op.drop_table("feature_unit_price", schema="core")
    op.drop_table("subscription_tier", schema="core")
    op.drop_table("ai_feature", schema="core")
    op.drop_table("service_catalog", schema="core")
