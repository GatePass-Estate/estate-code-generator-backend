"""add marketplace feature media paths

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-08-29 19:30:00.000000

GCS object paths for the parent product display picture and explanatory
video. Video streaming is wired later; the path is stored now.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add display picture and explanatory video GCS path columns."""
    op.add_column(
        "ai_marketplace_feature",
        sa.Column("display_picture_path", sa.Text(), nullable=True),
        schema="core",
    )
    op.add_column(
        "ai_marketplace_feature",
        sa.Column("display_picture_content_type", sa.String(), nullable=True),
        schema="core",
    )
    op.add_column(
        "ai_marketplace_feature",
        sa.Column("explanatory_video_path", sa.Text(), nullable=True),
        schema="core",
    )
    op.add_column(
        "ai_marketplace_feature",
        sa.Column(
            "explanatory_video_content_type", sa.String(), nullable=True
        ),
        schema="core",
    )


def downgrade() -> None:
    """Remove marketplace media path columns."""
    op.drop_column(
        "ai_marketplace_feature",
        "explanatory_video_content_type",
        schema="core",
    )
    op.drop_column(
        "ai_marketplace_feature",
        "explanatory_video_path",
        schema="core",
    )
    op.drop_column(
        "ai_marketplace_feature",
        "display_picture_content_type",
        schema="core",
    )
    op.drop_column(
        "ai_marketplace_feature",
        "display_picture_path",
        schema="core",
    )
