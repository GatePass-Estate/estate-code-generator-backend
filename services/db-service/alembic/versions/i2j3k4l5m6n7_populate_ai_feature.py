"""populate ai feature

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-09-13 14:21:00.000000

Replace Phase 1 test rows in core.ai_feature with the production AI
paid features.
"""

from typing import Any, Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "i2j3k4l5m6n7"
down_revision: Union[str, None] = "h1i2j3k4l5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AI_FEATURES: tuple[dict[str, Any], ...] = (
    {
        "feature_key": "access_anomaly_detection_tier_1",
        "name": "Access Code Anomaly Scan",
        "description": (
            "This feature runs anomaly scans in the background and triggers "
            "an alerts whenever a suspicious access is detected. It also "
            "allows admins to review all analysed instances in one place, "
            "with insights and transparency as to how the AI agent came to "
            "it's conclusion on each case."
        ),
    },
    {
        "feature_key": "access_anomaly_detection_tier_2",
        "name": "Anomaly Scan Results In-house AI Review",
        "description": (
            "This feature helps the admin quickly review each analysed case "
            "and generates a human readable report using our in-house AI "
            "Agents"
        ),
    },
    {
        "feature_key": "access_anomaly_detection_tier_3",
        "name": "Anomaly Scan Results Third-Party AI Review",
        "description": (
            "This feature helps the admin quickly review each analysed case "
            "and generates a human readable report using advanced "
            "third-party AI Agents"
        ),
    },
    {
        "feature_key": "incident_report_summary_tier_1",
        "name": "Incident Report Summary and Insights",
        "description": (
            "This feature helps admin to review incident reports all in one "
            "place with added insight from analysis conducted on the reports"
        ),
    },
    {
        "feature_key": "incident_report_summary_tier_2",
        "name": "Incident Report In-house AI Review",
        "description": (
            "This feature employs our in-house AI agents to quickly generate "
            "insight and uncover trends existing in the reports"
        ),
    },
    {
        "feature_key": "incident_report_summary_tier_3",
        "name": "Incident Report Third-Party AI Review",
        "description": (
            "This feature employs third-party AI agents to quickly generate "
            "insight and uncover trends existing in the reports"
        ),
    },
)

_FEATURE_KEYS = tuple(item["feature_key"] for item in _AI_FEATURES)


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def upgrade() -> None:
    """Clear old ai_feature rows, then insert the paid AI catalog."""
    _execute(
        "DELETE FROM core.feature_unit_price WHERE ai_feature_id IS NOT NULL"
    )
    _execute("DELETE FROM core.estate_ai_feature")
    _execute("DELETE FROM core.ai_feature")
    leftover = _execute("SELECT COUNT(*) FROM core.ai_feature").scalar()
    if leftover:
        raise RuntimeError(
            f"Failed to clear ai_feature: {leftover} rows remain"
        )
    op.bulk_insert(
        sa.table(
            "ai_feature",
            sa.column("id", sa.UUID),
            sa.column("feature_key", sa.String),
            sa.column("name", sa.String),
            sa.column("description", sa.Text),
            sa.column("is_free", sa.Boolean),
            sa.column("is_active", sa.Boolean),
            sa.column("is_deleted", sa.Boolean),
            schema="core",
        ),
        [
            {
                "id": uuid.uuid4(),
                "feature_key": item["feature_key"],
                "name": item["name"],
                "description": item["description"],
                "is_free": False,
                "is_active": True,
                "is_deleted": False,
            }
            for item in _AI_FEATURES
        ],
    )
    count = _execute("SELECT COUNT(*) FROM core.ai_feature").scalar()
    if int(count or 0) != len(_AI_FEATURES):
        raise RuntimeError("ai_feature seed row count mismatch")


def downgrade() -> None:
    """Remove rows this revision inserted. Cleared test rows stay gone."""
    keys_sql = ", ".join(f"'{key}'" for key in _FEATURE_KEYS)
    _execute(
        "DELETE FROM core.feature_unit_price WHERE ai_feature_id IN ("
        "  SELECT id FROM core.ai_feature"
        f"  WHERE feature_key IN ({keys_sql})"
        ")"
    )
    _execute(
        "DELETE FROM core.estate_ai_feature WHERE ai_feature_id IN ("
        "  SELECT id FROM core.ai_feature"
        f"  WHERE feature_key IN ({keys_sql})"
        ")"
    )
    _execute(f"DELETE FROM core.ai_feature WHERE feature_key IN ({keys_sql})")
