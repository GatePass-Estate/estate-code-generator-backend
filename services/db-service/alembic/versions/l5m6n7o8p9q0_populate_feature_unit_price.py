"""populate feature unit price

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-09-13 14:24:00.000000

Write NG/NGN core.feature_unit_price rows from the catalog Total Price
column for each paid service and AI feature.
"""

import uuid
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COUNTRY = "NIGERIA"
_CURRENCY = "NGN"

_SERVICE_PRICES: tuple[tuple[str, int], ...] = (
    ("administrative_fee", 70),
    ("extended_historical_record", 70),
    ("guest_management", 70),
    ("incident_report", 140),
    ("admin_broadcast", 140),
    ("advanced_code_management", 140),
)

_AI_PRICES: tuple[tuple[str, int], ...] = (
    ("access_anomaly_detection_tier_1", 5000),
    ("access_anomaly_detection_tier_2", 6500),
    ("access_anomaly_detection_tier_3", 15000),
    ("incident_report_summary_tier_1", 2500),
    ("incident_report_summary_tier_2", 6500),
    ("incident_report_summary_tier_3", 15000),
)


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def _lookup_id(table: str, key_column: str, key: str) -> uuid.UUID:
    """Resolve a previously seeded row id by natural key."""
    row = _execute(
        f"SELECT id FROM core.{table}"
        f" WHERE {key_column} = :key AND COALESCE(is_deleted, false) = false"
        " LIMIT 1",
        {"key": key},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing seed row core.{table}.{key_column}={key}")
    return row[0]


def upgrade() -> None:
    """Clear leftover prices, then insert NG/NGN unit prices."""
    _execute("DELETE FROM core.feature_unit_price")
    leftover = _execute(
        "SELECT COUNT(*) FROM core.feature_unit_price"
    ).scalar()
    if leftover:
        raise RuntimeError(
            f"Failed to clear feature_unit_price: {leftover} rows remain"
        )
    service_ids = {
        key: _lookup_id("service_catalog", "service_key", key)
        for key, _price in _SERVICE_PRICES
    }
    ai_ids = {
        key: _lookup_id("ai_feature", "feature_key", key)
        for key, _price in _AI_PRICES
    }
    price_rows: list[dict[str, Any]] = []
    for key, price in _SERVICE_PRICES:
        price_rows.append(
            {
                "id": uuid.uuid4(),
                "country_code": _COUNTRY,
                "currency_code": _CURRENCY,
                "feature_kind": "service",
                "service_catalog_id": service_ids[key],
                "ai_feature_id": None,
                "feature_unit_price": price,
                "is_active": True,
                "is_deleted": False,
            }
        )
    for key, price in _AI_PRICES:
        price_rows.append(
            {
                "id": uuid.uuid4(),
                "country_code": _COUNTRY,
                "currency_code": _CURRENCY,
                "feature_kind": "ai",
                "service_catalog_id": None,
                "ai_feature_id": ai_ids[key],
                "feature_unit_price": price,
                "is_active": True,
                "is_deleted": False,
            }
        )
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
    expected = len(_SERVICE_PRICES) + len(_AI_PRICES)
    count = _execute("SELECT COUNT(*) FROM core.feature_unit_price").scalar()
    if int(count or 0) != expected:
        raise RuntimeError("feature_unit_price seed row count mismatch")


def downgrade() -> None:
    """Remove prices this revision inserted. Cleared test rows stay gone."""
    service_keys = ", ".join(f"'{key}'" for key, _price in _SERVICE_PRICES)
    ai_keys = ", ".join(f"'{key}'" for key, _price in _AI_PRICES)
    _execute(
        "DELETE FROM core.feature_unit_price WHERE"
        " service_catalog_id IN ("
        "  SELECT id FROM core.service_catalog"
        f"  WHERE service_key IN ({service_keys})"
        " ) OR ai_feature_id IN ("
        "  SELECT id FROM core.ai_feature"
        f"  WHERE feature_key IN ({ai_keys})"
        ")"
    )
