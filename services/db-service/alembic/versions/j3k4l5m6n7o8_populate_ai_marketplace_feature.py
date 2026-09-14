"""populate ai marketplace feature

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-09-13 14:22:00.000000

Populate core.ai_marketplace_feature from the AI parent feature column.
Child tier ids are looked up from core.ai_feature.
"""

from typing import Any, Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, None] = "i2j3k4l5m6n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MARKETPLACE: tuple[dict[str, Any], ...] = (
    {
        "name": "Access Anomaly Detection",
        "category": "Access Anomaly Detection",
        "description": (
            "Background anomaly scans for suspicious access, with admin "
            "review and optional in-house or third-party AI case reports."
        ),
        "children": (
            ("tier_1", "access_anomaly_detection_tier_1"),
            ("tier_2", "access_anomaly_detection_tier_2"),
            ("tier_3", "access_anomaly_detection_tier_3"),
        ),
    },
    {
        "name": "Incident Report Insights",
        "category": "Incident Report Insights",
        "description": (
            "Incident report review with analysis, plus optional in-house "
            "or third-party AI insight and trend reports."
        ),
        "children": (
            ("tier_1", "incident_report_summary_tier_1"),
            ("tier_2", "incident_report_summary_tier_2"),
            ("tier_3", "incident_report_summary_tier_3"),
        ),
    },
)

_MARKETPLACE_NAMES = tuple(item["name"] for item in _MARKETPLACE)


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def _lookup_ai_id(feature_key: str) -> uuid.UUID:
    """Resolve a previously seeded ai_feature id by feature_key."""
    row = _execute(
        "SELECT id FROM core.ai_feature"
        " WHERE feature_key = :key AND COALESCE(is_deleted, false) = false"
        " LIMIT 1",
        {"key": feature_key},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing ai_feature.feature_key={feature_key}")
    return row[0]


def upgrade() -> None:
    """Clear old marketplace products, then insert parent catalog rows."""
    _execute("DELETE FROM core.ai_marketplace_feature_rating")
    _execute("DELETE FROM core.ai_marketplace_feature")
    leftover = _execute(
        "SELECT COUNT(*) FROM core.ai_marketplace_feature"
    ).scalar()
    if leftover:
        raise RuntimeError(
            f"Failed to clear ai_marketplace_feature: {leftover} rows remain"
        )
    rows = []
    for product in _MARKETPLACE:
        tiers = [
            {
                "tier": tier,
                "ai_feature_id": str(_lookup_ai_id(feature_key)),
            }
            for tier, feature_key in product["children"]
        ]
        rows.append(
            {
                "id": uuid.uuid4(),
                "name": product["name"],
                "description": product["description"],
                "category": product["category"],
                "is_active": True,
                "tiers": tiers,
                "is_deleted": False,
            }
        )
    op.bulk_insert(
        sa.table(
            "ai_marketplace_feature",
            sa.column("id", sa.UUID),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("category", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("tiers", postgresql.JSONB),
            sa.column("is_deleted", sa.Boolean),
            schema="core",
        ),
        rows,
    )
    count = _execute(
        "SELECT COUNT(*) FROM core.ai_marketplace_feature"
    ).scalar()
    if int(count or 0) != len(_MARKETPLACE):
        raise RuntimeError("ai_marketplace_feature seed row count mismatch")


def downgrade() -> None:
    """Remove rows this revision inserted. Cleared test rows stay gone."""
    names_sql = ", ".join(f"'{name}'" for name in _MARKETPLACE_NAMES)
    _execute(
        "DELETE FROM core.ai_marketplace_feature_rating"
        " WHERE ai_marketplace_feature_id IN ("
        "  SELECT id FROM core.ai_marketplace_feature"
        f"  WHERE name IN ({names_sql})"
        ")"
    )
    _execute(
        "DELETE FROM core.ai_marketplace_feature"
        f" WHERE name IN ({names_sql})"
    )
