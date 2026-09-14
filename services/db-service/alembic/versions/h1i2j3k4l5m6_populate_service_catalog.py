"""populate service catalog

Revision ID: h1i2j3k4l5m6
Revises: g7h8i9j0k1l2
Create Date: 2026-09-13 14:20:00.000000

Replace Phase 1 test rows in core.service_catalog with the production
non-AI paid features. Free features are not stored.
"""

import uuid
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SERVICES: tuple[dict[str, Any], ...] = (
    {
        "service_key": "administrative_fee",
        "name": "Administrative Fee",
        "description": "Per-user administrative fee charged with paid plans.",
        "limit_type": "boolean",
    },
    {
        "service_key": "extended_historical_record",
        "name": "Extended Historical Records",
        "description": (
            "This feature allows users access logs from longer historical "
            "periods"
        ),
        "limit_type": "duration_days",
    },
    {
        "service_key": "guest_management",
        "name": "Guest Management",
        "description": (
            "This feature allows users to save guest for quick and repeated "
            "access management"
        ),
        "limit_type": "boolean",
    },
    {
        "service_key": "incident_report",
        "name": "Incident Reporting and Review",
        "description": (
            "This feature allows users to report incidents, and admins are "
            "able to view reported reports and manage them."
        ),
        "limit_type": "boolean",
    },
    {
        "service_key": "admin_broadcast",
        "name": "Broadcasts and Announcements",
        "description": (
            "This feature allows facility admins to broadcast messages to "
            "specified users in the same facility"
        ),
        "limit_type": "boolean",
    },
    {
        "service_key": "advanced_code_management",
        "name": "Advanced Code Management",
        "description": (
            "This feature introduces complete flexibility to access "
            "management. Users are able to schedule code for a future point "
            "in time, create access code valid for extended periods, extend "
            "access codes close to expiry without regeneration, set daily "
            "validity periods for an access code during generation, freeze "
            "and unfreeze an active code, and regenerate code from the "
            "history log."
        ),
        "limit_type": "boolean",
    },
)

_SERVICE_KEYS = tuple(item["service_key"] for item in _SERVICES)


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def upgrade() -> None:
    """Clear old service_catalog rows, then insert the paid catalog."""
    _execute(
        "DELETE FROM core.feature_unit_price"
        " WHERE service_catalog_id IS NOT NULL"
    )
    _execute("DELETE FROM core.service_catalog")
    leftover = _execute("SELECT COUNT(*) FROM core.service_catalog").scalar()
    if leftover:
        raise RuntimeError(
            f"Failed to clear service_catalog: {leftover} rows remain"
        )
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
                "id": uuid.uuid4(),
                "service_key": item["service_key"],
                "name": item["name"],
                "description": item["description"],
                "limit_type": item["limit_type"],
                "is_active": True,
                "is_deleted": False,
            }
            for item in _SERVICES
        ],
    )
    count = _execute("SELECT COUNT(*) FROM core.service_catalog").scalar()
    if int(count or 0) != len(_SERVICES):
        raise RuntimeError("service_catalog seed row count mismatch")


def downgrade() -> None:
    """Remove rows this revision inserted. Cleared test rows stay gone."""
    keys_sql = ", ".join(f"'{key}'" for key in _SERVICE_KEYS)
    _execute(
        "DELETE FROM core.feature_unit_price WHERE service_catalog_id IN ("
        "  SELECT id FROM core.service_catalog"
        f"  WHERE service_key IN ({keys_sql})"
        ")"
    )
    _execute(
        f"DELETE FROM core.service_catalog WHERE service_key IN ({keys_sql})"
    )
