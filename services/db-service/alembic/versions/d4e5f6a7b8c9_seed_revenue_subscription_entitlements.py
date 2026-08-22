"""seed revenue subscription entitlements

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-11 08:03:00.000000

Seeds core.subscription_tier and NG/NGN core.feature_unit_price rows for
the minimal catalog used in Phase 1 testing (administrative_fee,
visitor_log_retention_days, resident_log_retention_days,
visitor_resident_anomaly_detection).
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIER_SLUGS = ("access", "watch", "sentinel", "command", "custom")

_NG_PRICE_IDS = (
    "price.NG.service.administrative_fee",
    "price.NG.service.visitor_log_retention_days",
    "price.NG.service.resident_log_retention_days",
    "price.NG.ai.visitor_resident_anomaly_detection",
)


def _uid(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"gatepass.revenue.{name}")


def upgrade() -> None:
    """Insert subscription_tier and feature_unit_price seed rows."""
    # Minimal entitlements: only keys present in the slim service_catalog.
    access_ents = {
        "administrative_fee": False,
        "visitor_log_retention_days": 7,
        "resident_log_retention_days": 7,
    }
    paid_ents = {
        "administrative_fee": True,
        "visitor_log_retention_days": 365,
        "resident_log_retention_days": 365,
    }
    anomaly_ai = ["visitor_resident_anomaly_detection"]

    tier_rows = [
        {
            "id": _uid("tier.access"),
            "slug": "access",
            "name": "Access (Free)",
            "display_order": 0,
            "entitlements": access_ents,
            "included_ai_features": [],
            "is_custom": False,
            "is_active": True,
            "billing_unit_hint": "residential",
            "is_deleted": False,
        },
        {
            "id": _uid("tier.watch"),
            "slug": "watch",
            "name": "Watch",
            "display_order": 1,
            "entitlements": paid_ents,
            "included_ai_features": [],
            "is_custom": False,
            "is_active": True,
            "billing_unit_hint": "residential",
            "is_deleted": False,
        },
        {
            "id": _uid("tier.sentinel"),
            "slug": "sentinel",
            "name": "Sentinel",
            "display_order": 2,
            "entitlements": paid_ents,
            "included_ai_features": anomaly_ai,
            "is_custom": False,
            "is_active": True,
            "billing_unit_hint": "residential",
            "is_deleted": False,
        },
        {
            "id": _uid("tier.command"),
            "slug": "command",
            "name": "Command",
            "display_order": 3,
            "entitlements": paid_ents,
            "included_ai_features": anomaly_ai,
            "is_custom": False,
            "is_active": True,
            "billing_unit_hint": "residential",
            "is_deleted": False,
        },
        {
            "id": _uid("tier.custom"),
            "slug": "custom",
            "name": "Custom",
            "display_order": 4,
            "entitlements": {},
            "included_ai_features": [],
            "is_custom": True,
            "is_active": True,
            "billing_unit_hint": None,
            "is_deleted": False,
        },
    ]
    op.bulk_insert(
        sa.table(
            "subscription_tier",
            sa.column("id", sa.UUID),
            sa.column("slug", sa.String),
            sa.column("name", sa.String),
            sa.column("display_order", sa.Integer),
            sa.column("entitlements", postgresql.JSONB),
            sa.column("included_ai_features", postgresql.ARRAY(sa.Text())),
            sa.column("is_custom", sa.Boolean),
            sa.column("is_active", sa.Boolean),
            sa.column("billing_unit_hint", sa.String),
            sa.column("is_deleted", sa.Boolean),
            schema="core",
        ),
        tier_rows,
    )

    # Illustrative NG prices for the slim catalog:
    # visitor 400 + resident 400 + administrative_fee 700 = 1500/seat
    # + anomaly AI 500 flat for Sentinel/Command quotes.
    price_rows = [
        {
            "id": _uid("price.NG.service.administrative_fee"),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "service",
            "service_catalog_id": _uid("service.administrative_fee"),
            "ai_feature_id": None,
            "feature_unit_price": 700,
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": _uid("price.NG.service.visitor_log_retention_days"),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "service",
            "service_catalog_id": _uid("service.visitor_log_retention_days"),
            "ai_feature_id": None,
            "feature_unit_price": 400,
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": _uid("price.NG.service.resident_log_retention_days"),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "service",
            "service_catalog_id": _uid("service.resident_log_retention_days"),
            "ai_feature_id": None,
            "feature_unit_price": 400,
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": _uid("price.NG.ai.visitor_resident_anomaly_detection"),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "ai",
            "service_catalog_id": None,
            "ai_feature_id": _uid("ai.visitor_resident_anomaly_detection"),
            "feature_unit_price": 500,
            "is_active": True,
            "is_deleted": False,
        },
    ]
    op.bulk_insert(
        sa.table(
            "feature_unit_price",
            sa.column("id", sa.UUID),
            sa.column("country_code", sa.String),
            sa.column("currency_code", sa.String),
            sa.column("feature_kind", sa.String),
            sa.column("service_catalog_id", sa.UUID),
            sa.column("ai_feature_id", sa.UUID),
            sa.column("feature_unit_price", sa.Numeric),
            sa.column("is_active", sa.Boolean),
            sa.column("is_deleted", sa.Boolean),
            schema="core",
        ),
        price_rows,
    )


def downgrade() -> None:
    """Remove seeded subscription_tier and feature_unit_price rows."""
    price_ids_sql = ", ".join(f"'{_uid(name)}'" for name in _NG_PRICE_IDS)
    op.execute(
        "DELETE FROM core.feature_unit_price"
        f" WHERE country_code = 'NG' AND id IN ({price_ids_sql})"
    )
    slugs_sql = ", ".join(f"'{slug}'" for slug in _TIER_SLUGS)
    op.execute(
        f"DELETE FROM core.subscription_tier WHERE slug IN ({slugs_sql})"
    )
