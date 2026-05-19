"""Add incident report table for estate incident filings.

Revision ID: c17962ae653d
Revises: 628632808fd8
Create Date: 2026-05-17 11:53:39.510875

Creates ``core.incidentreport`` with optional ``title``, optional
``custom_category``, and ``category`` as an array of ``incident_category``
enum values.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "c17962ae653d"
down_revision: Union[str, None] = "628632808fd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INCIDENT_CATEGORY_VALUES = (
    "security",
    "access_control",
    "noise_disturbance",
    "property_damage",
    "maintenance",
    "fire_safety",
    "medical_emergency",
    "theft",
    "harassment",
    "dispute",
    "unauthorized_access",
    "other",
)

_incident_category_enum = postgresql.ENUM(
    *_INCIDENT_CATEGORY_VALUES,
    name="incident_category",
    schema="core",
    create_type=False,
)


def upgrade() -> None:
    """Create incident-category enum and ``core.incidentreport`` table."""
    _incident_category_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "incidentreport",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column(
            "estate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.estates.id"),
            nullable=False,
        ),
        sa.Column(
            "reported_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column(
            "category",
            postgresql.ARRAY(_incident_category_enum),
            nullable=False,
            server_default=sa.text("'{}'::core.incident_category[]"),
        ),
        sa.Column("custom_category", sa.String(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=func.timezone("UTC", func.now()),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        "ix_core_incidentreport_estate_id",
        "incidentreport",
        ["estate_id"],
        schema="core",
    )
    op.create_index(
        "ix_core_incidentreport_reported_by_user_id",
        "incidentreport",
        ["reported_by_user_id"],
        schema="core",
    )


def downgrade() -> None:
    """Drop ``core.incidentreport`` and incident-category enum."""
    op.drop_index(
        "ix_core_incidentreport_reported_by_user_id",
        table_name="incidentreport",
        schema="core",
    )
    op.drop_index(
        "ix_core_incidentreport_estate_id",
        table_name="incidentreport",
        schema="core",
    )
    op.drop_table("incidentreport", schema="core")
    _incident_category_enum.drop(op.get_bind(), checkfirst=True)
