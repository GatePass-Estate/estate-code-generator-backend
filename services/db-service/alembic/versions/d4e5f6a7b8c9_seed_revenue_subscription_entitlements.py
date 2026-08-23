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

_SERVICE_PRICE_KEYS = (
    "administrative_fee",
    "visitor_log_retention_days",
    "resident_log_retention_days",
)
_AI_PRICE_KEYS = ("visitor_resident_anomaly_detection",)


def _lookup_id(table: str, key_column: str, key: str) -> uuid.UUID:
    """Resolve a previously seeded row id by natural key."""
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            f"SELECT id FROM core.{table}"
            f" WHERE {key_column} = :key AND is_deleted = false"
            " LIMIT 1"
        ),
        {"key": key},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing seed row core.{table}.{key_column}={key}")
    return row[0]


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
            "id": uuid.uuid4(),
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
            "id": uuid.uuid4(),
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
            "id": uuid.uuid4(),
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
            "id": uuid.uuid4(),
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
            "id": uuid.uuid4(),
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

    service_ids = {
        key: _lookup_id("service_catalog", "service_key", key)
        for key in _SERVICE_PRICE_KEYS
    }
    ai_ids = {
        key: _lookup_id("ai_feature", "feature_key", key)
        for key in _AI_PRICE_KEYS
    }

    # Illustrative NG prices for the slim catalog:
    # visitor 400 + resident 400 + administrative_fee 700 = 1500/seat
    # + anomaly AI 500 flat for Sentinel/Command quotes.
    price_rows = [
        {
            "id": uuid.uuid4(),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "service",
            "service_catalog_id": service_ids["administrative_fee"],
            "ai_feature_id": None,
            "feature_unit_price": 700,
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": uuid.uuid4(),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "service",
            "service_catalog_id": service_ids["visitor_log_retention_days"],
            "ai_feature_id": None,
            "feature_unit_price": 400,
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": uuid.uuid4(),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "service",
            "service_catalog_id": service_ids["resident_log_retention_days"],
            "ai_feature_id": None,
            "feature_unit_price": 400,
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": uuid.uuid4(),
            "country_code": "NG",
            "currency_code": "NGN",
            "feature_kind": "ai",
            "service_catalog_id": None,
            "ai_feature_id": ai_ids["visitor_resident_anomaly_detection"],
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
    service_keys_sql = ", ".join(f"'{key}'" for key in _SERVICE_PRICE_KEYS)
    ai_keys_sql = ", ".join(f"'{key}'" for key in _AI_PRICE_KEYS)
    op.execute(
        "DELETE FROM core.feature_unit_price"
        " WHERE country_code = 'NG'"
        " AND ("
        "  service_catalog_id IN ("
        "    SELECT id FROM core.service_catalog"
        f"    WHERE service_key IN ({service_keys_sql})"
        "  )"
        "  OR ai_feature_id IN ("
        "    SELECT id FROM core.ai_feature"
        f"    WHERE feature_key IN ({ai_keys_sql})"
        "  )"
        ")"
    )
    slugs_sql = ", ".join(f"'{slug}'" for slug in _TIER_SLUGS)
    op.execute(
        f"DELETE FROM core.subscription_tier WHERE slug IN ({slugs_sql})"
    )
