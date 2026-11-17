"""standalone ai subscription fix

Revision ID: 908a9b2d91d1
Revises: e7162dc65493
Create Date: 2026-09-28 15:15:51.134752

Add columns to support standalone AI subscription auto-renewal and
pre-expiry notifications:
  - core.ai_feature.paystack_plan_code
  - core.estate_ai_feature.paystack_subscription_code
  - core.estate_ai_feature.pre_expiry_notified
  - core.estate_subscription.pre_expiry_notified

Also seeds max_active_users onto the access tier entitlements JSONB
so the over-cap lock triggers correctly on subscription expiry.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "908a9b2d91d1"
down_revision: Union[str, None] = "e7162dc65493"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- core.ai_feature --------------------------------------------------
    op.add_column(
        "ai_feature",
        sa.Column("paystack_plan_code", sa.String(), nullable=True),
        schema="core",
    )

    # -- core.estate_ai_feature -------------------------------------------
    op.add_column(
        "estate_ai_feature",
        sa.Column("paystack_subscription_code", sa.String(), nullable=True),
        schema="core",
    )
    op.add_column(
        "estate_ai_feature",
        sa.Column(
            "pre_expiry_notified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        schema="core",
    )

    # -- core.estate_subscription -----------------------------------------
    op.add_column(
        "estate_subscription",
        sa.Column(
            "pre_expiry_notified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        schema="core",
    )

    # -- notificationtype enum additions ------------------------------------------
    for value in [
        # Subscription lifecycle (added manually before; guard with IF NOT EXISTS)
        "SUBSCRIPTION_PAYMENT_FAILED",
        "SUBSCRIPTION_GRACE_PERIOD",
        "SUBSCRIPTION_GRACE_PERIOD_ADMIN",
        "SUBSCRIPTION_EXPIRED",
        # New: pre-expiry reminders + standalone AI grant lifecycle
        "SUBSCRIPTION_RENEWAL_REMINDER",
        "AI_GRANT_RENEWAL_REMINDER",
        "AI_GRANT_GRACE_PERIOD",
        "AI_GRANT_GRACE_PERIOD_ADMIN",
        "AI_GRANT_EXPIRED",
        "AI_GRANT_PAYMENT_FAILED",
    ]:
        op.execute(
            f"ALTER TYPE core.notificationtype ADD VALUE IF NOT EXISTS '{value}'"
        )

    # -- seed max_active_users on access tier
    op.execute(
        """
        UPDATE core.subscription_tier
        SET entitlements = entitlements
            || '{"max_active_users": 10}'::jsonb
        WHERE slug = 'access'
          AND NOT (entitlements ? 'max_active_users')
        """
    )


def downgrade() -> None:
    op.drop_column("estate_subscription", "pre_expiry_notified", schema="core")
    op.drop_column("estate_ai_feature", "pre_expiry_notified", schema="core")
    op.drop_column(
        "estate_ai_feature", "paystack_subscription_code", schema="core"
    )
    op.drop_column("ai_feature", "paystack_plan_code", schema="core")
    # Note: max_active_users is NOT removed on downgrade — removing an
    # entitlement key from existing live data is destructive and would
    # immediately affect access checks.
