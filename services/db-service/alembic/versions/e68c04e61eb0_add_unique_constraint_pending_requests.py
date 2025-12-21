"""add_unique_constraint_pending_requests

Revision ID: e68c04e61eb0
Revises: 82eb957faeeb
Create Date: 2025-12-02 15:48:29.641068

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e68c04e61eb0"
down_revision: Union[str, None] = "82eb957faeeb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Adds a unique partial index to prevent duplicate pending requests
    for the same user and request type.
    """
    # First, identify and handle any existing duplicate pending requests
    # Keep only the most recent pending request per user+request_type
    op.execute("""
        UPDATE core.requests r1
        SET status = 'REJECTED'
        WHERE status = 'PENDING'
        AND EXISTS (
            SELECT 1
            FROM core.requests r2
            WHERE r2.resident_id = r1.resident_id
            AND r2.request_type = r1.request_type
            AND r2.status = 'PENDING'
            AND r2.created_at > r1.created_at
        )
    """)

    # Create a unique partial index on (resident_id, request_type)
    # where status = 'PENDING'
    # This prevents duplicate pending requests for the same field
    op.execute("""
        CREATE UNIQUE INDEX idx_unique_pending_request
        ON core.requests (resident_id, request_type)
        WHERE status = 'PENDING' AND is_deleted = FALSE
    """)


def downgrade() -> None:
    """
    Downgrade schema.

    Removes the unique partial index that prevents duplicate pending requests.
    """
    op.execute("DROP INDEX IF EXISTS core.idx_unique_pending_request")
