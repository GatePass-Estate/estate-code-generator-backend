"""add subscription tier description

Revision ID: p9q0r1s2t3u
Revises: o8p9q0r1s2t
Create Date: 2026-09-27 12:15:00.000000

Add ``description`` to ``core.subscription_tier`` and fill each seeded
tier with a sentence of at least fourteen words.
"""

from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p9q0r1s2t3u"
down_revision: Union[str, None] = "o8p9q0r1s2t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DESCRIPTIONS: dict[str, str] = {
    "access": (
        "The entry plan for an estate, covering core access without paid "
        "guest tools, incident reporting, broadcasts, or bundled AI features."
    ),
    "watch": (
        "Adds guest management, incident reports, admin broadcasts, and "
        "advanced codes, with ninety days of extended access history and "
        "no bundled AI."
    ),
    "sentinel": (
        "Includes everything in Watch, one hundred eighty days of access "
        "history, and the first tier of access anomaly and incident report "
        "insights."
    ),
    "command": (
        "Includes everything in Sentinel, a full year of access history, "
        "and in-house AI reviews for both access anomalies and incident "
        "reports."
    ),
    "custom": (
        "A tailored estate plan whose services and AI features are set for "
        "that community instead of using a fixed Watch, Sentinel, or "
        "Command bundle."
    ),
}


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def upgrade() -> None:
    """Add the description column and fill each seeded tier."""
    op.add_column(
        "subscription_tier",
        sa.Column(
            "description",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        schema="core",
    )
    for slug, description in _DESCRIPTIONS.items():
        words = description.split()
        if len(words) < 14:
            raise RuntimeError(
                f"{slug} description has {len(words)} words; need at least 14"
            )
        _execute(
            "UPDATE core.subscription_tier"
            " SET description = :description"
            " WHERE slug = :slug"
            " AND COALESCE(is_deleted, false) = false",
            {"slug": slug, "description": description},
        )


def downgrade() -> None:
    """Drop the subscription tier description column."""
    op.drop_column("subscription_tier", "description", schema="core")
