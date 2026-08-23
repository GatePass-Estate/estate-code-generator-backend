"""seed revenue service catalog

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-11 08:01:00.000000

Seeds a minimal core.service_catalog set for revenue Phase 1 testing.
Expand to the full feature list once tests pass.
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SERVICE_KEYS = (
    "administrative_fee",
    "visitor_log_retention_days",
    "resident_log_retention_days",
)


def upgrade() -> None:
    """Insert minimal service_catalog seed rows."""
    service_rows = [
        {
            "id": uuid.uuid4(),
            "service_key": "administrative_fee",
            "name": "Administrative Fee",
            "description": None,
            "limit_type": "boolean",
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": uuid.uuid4(),
            "service_key": "visitor_log_retention_days",
            "name": "Visitor Log Retention Days",
            "description": None,
            "limit_type": "int",
            "is_active": True,
            "is_deleted": False,
        },
        {
            "id": uuid.uuid4(),
            "service_key": "resident_log_retention_days",
            "name": "Resident Log Retention Days",
            "description": None,
            "limit_type": "int",
            "is_active": True,
            "is_deleted": False,
        },
    ]
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
        service_rows,
    )


def downgrade() -> None:
    """Remove seeded service_catalog rows."""
    keys_sql = ", ".join(f"'{key}'" for key in _SERVICE_KEYS)
    op.execute(
        f"DELETE FROM core.service_catalog WHERE service_key IN ({keys_sql})"
    )
