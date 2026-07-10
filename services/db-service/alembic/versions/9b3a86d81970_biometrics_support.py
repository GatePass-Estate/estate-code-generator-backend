"""biometrics_support

Revision ID: 9b3a86d81970
Revises: a49c88181154
Create Date: 2026-07-10 14:45:01.484159

Adds ``biometric_token_hash`` to ``core.sessions`` — a SHA-256 hex digest
of the biometric token stored by the FE in device SecureStore.  NULL means
biometric login is not enabled for this session.  The index enables fast
lookup during biometric token exchange.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b3a86d81970"
down_revision: Union[str, None] = "a49c88181154"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add biometric_token_hash column and index to core.sessions."""
    op.add_column(
        "sessions",
        sa.Column("biometric_token_hash", sa.Text(), nullable=True),
        schema="core",
    )
    op.create_index(
        "ix_core_sessions_biometric_token_hash",
        "sessions",
        ["biometric_token_hash"],
        schema="core",
    )


def downgrade() -> None:
    """Remove biometric_token_hash index and column from core.sessions."""
    op.drop_index(
        "ix_core_sessions_biometric_token_hash",
        table_name="sessions",
        schema="core",
    )
    op.drop_column("sessions", "biometric_token_hash", schema="core")
