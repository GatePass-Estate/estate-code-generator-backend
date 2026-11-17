"""seed vat service and price

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-09-14 08:40:00.000000

Add service_catalog.vat and a Nigeria feature_unit_price row (7.5 percent).
"""

import uuid
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m6n7o8p9q0r1"
down_revision: Union[str, None] = "l5m6n7o8p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VAT_KEY = "vat"


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def upgrade() -> None:
    """Insert VAT as a service_key and its Nigeria unit-price (percent)."""
    catalog_id = uuid.uuid4()
    op.bulk_insert(
        sa.table(
            "service_catalog",
            sa.column("id", sa.UUID),
            sa.column("service_key", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("limit_type", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("is_deleted", sa.Boolean),
            schema="core",
        ),
        [
            {
                "id": catalog_id,
                "service_key": _VAT_KEY,
                "name": "VAT",
                "description": (
                    "Value-added tax rate (percent) applied after quote "
                    "subtotal."
                ),
                "limit_type": "boolean",
                "is_active": True,
                "is_deleted": False,
            }
        ],
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
        [
            {
                "id": uuid.uuid4(),
                "country_code": "NIGERIA",
                "currency_code": "NGN",
                "feature_kind": "service",
                "service_catalog_id": catalog_id,
                "ai_feature_id": None,
                "feature_unit_price": 7.5,
                "is_active": True,
                "is_deleted": False,
            }
        ],
    )


def downgrade() -> None:
    """Remove the VAT price row and catalog entry."""
    _execute(
        "DELETE FROM core.feature_unit_price WHERE service_catalog_id IN ("
        "  SELECT id FROM core.service_catalog WHERE service_key = :key"
        ")",
        {"key": _VAT_KEY},
    )
    _execute(
        "DELETE FROM core.service_catalog WHERE service_key = :key",
        {"key": _VAT_KEY},
    )
