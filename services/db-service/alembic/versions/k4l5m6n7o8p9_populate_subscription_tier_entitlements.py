"""populate subscription tier entitlements

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2026-09-13 14:23:00.000000

Write Watch / Sentinel / Command entitlements from the service catalog
sheet. Access is present with empty entitlements. Custom is left as-is.
"""

from typing import Any, Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, None] = "j3k4l5m6n7o8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHARED_PAID = {
    "administrative_fee": True,
    "guest_management": True,
    "incident_report": True,
    "admin_broadcast": True,
    "advanced_code_management": True,
}

_TIER_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    "access": {},
    "watch": {**_SHARED_PAID, "extended_historical_record": 90},
    "sentinel": {**_SHARED_PAID, "extended_historical_record": 180},
    "command": {**_SHARED_PAID, "extended_historical_record": 365},
}

_TIER_AI: dict[str, list[str]] = {
    "access": [],
    "watch": [],
    "sentinel": [
        "access_anomaly_detection_tier_1",
        "incident_report_summary_tier_1",
    ],
    "command": [
        "access_anomaly_detection_tier_1",
        "access_anomaly_detection_tier_2",
        "incident_report_summary_tier_1",
        "incident_report_summary_tier_2",
    ],
}

_TIER_META: dict[str, dict[str, Any]] = {
    "access": {
        "name": "Access",
        "display_order": 0,
        "billing_unit_hint": "residential",
    },
    "watch": {
        "name": "Watch",
        "display_order": 1,
        "billing_unit_hint": "residential",
    },
    "sentinel": {
        "name": "Sentinel",
        "display_order": 2,
        "billing_unit_hint": "residential",
    },
    "command": {
        "name": "Command",
        "display_order": 3,
        "billing_unit_hint": "residential",
    },
}


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def _tier_exists(slug: str) -> bool:
    """Return True when a subscription_tier row exists for ``slug``."""
    row = _execute(
        "SELECT 1 FROM core.subscription_tier WHERE slug = :slug LIMIT 1",
        {"slug": slug},
    ).fetchone()
    return row is not None


def upgrade() -> None:
    """Upsert Access and paid-tier entitlements. Leave Custom unchanged."""
    conn = op.get_bind()
    update_stmt = sa.text(
        """
        UPDATE core.subscription_tier
        SET entitlements = :entitlements,
            included_ai_features = :included_ai_features,
            name = :name,
            display_order = :display_order,
            is_custom = false,
            is_active = true,
            is_deleted = false,
            deleted_at = NULL,
            billing_unit_hint = :billing_unit_hint,
            updated_at = timezone('UTC', now())
        WHERE slug = :slug
        """
    ).bindparams(
        sa.bindparam("entitlements", type_=postgresql.JSONB),
        sa.bindparam(
            "included_ai_features",
            type_=postgresql.ARRAY(sa.Text()),
        ),
    )
    insert_stmt = sa.text(
        """
        INSERT INTO core.subscription_tier (
            id, slug, name, display_order, entitlements,
            included_ai_features, is_custom, is_active, billing_unit_hint,
            is_deleted
        ) VALUES (
            :id, :slug, :name, :display_order, :entitlements,
            :included_ai_features, false, true, :billing_unit_hint, false
        )
        """
    ).bindparams(
        sa.bindparam("entitlements", type_=postgresql.JSONB),
        sa.bindparam(
            "included_ai_features",
            type_=postgresql.ARRAY(sa.Text()),
        ),
    )
    for slug, ai_keys in _TIER_AI.items():
        meta = _TIER_META[slug]
        params = {
            "slug": slug,
            "name": meta["name"],
            "display_order": meta["display_order"],
            "entitlements": _TIER_ENTITLEMENTS[slug],
            "included_ai_features": ai_keys,
            "billing_unit_hint": meta["billing_unit_hint"],
        }
        if _tier_exists(slug):
            conn.execute(update_stmt, params)
        else:
            conn.execute(insert_stmt, {**params, "id": uuid.uuid4()})


def downgrade() -> None:
    """Tier updates overwrite existing rows and are not reversed."""
    pass
