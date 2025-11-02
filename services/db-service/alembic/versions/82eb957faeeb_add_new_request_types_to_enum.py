"""add_new_request_types_to_enum

Revision ID: 82eb957faeeb
Revises: 25b7ecb91ef8
Create Date: 2025-11-02 12:49:45.391722

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "82eb957faeeb"
down_revision: Union[str, None] = "25b7ecb91ef8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


new_requesttype = postgresql.ENUM(
    "FIRST_NAME_CHANGE",
    "LAST_NAME_CHANGE",
    "HOME_ADDRESS_CHANGE",
    "EMAIL_CHANGE",
    "PHONE_NUMBER_CHANGE",
    "GENDER_CHANGE",
    "VACATE_RESIDENCE",
    name="requesttype_new",
    schema="core",
)


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create the new enum type with correct values
    new_requesttype.create(op.get_bind(), checkfirst=True)

    # Step 2: Alter the column to use VARCHAR temporarily
    op.execute("""
        ALTER TABLE core.requests
        ALTER COLUMN request_type TYPE VARCHAR
        USING request_type::TEXT
    """)

    # Step 3: Drop the old enum type
    op.execute("DROP TYPE IF EXISTS core.requesttype CASCADE")

    # Step 4: Rename the new enum to the original name
    op.execute("ALTER TYPE core.requesttype_new RENAME TO requesttype")

    # Step 5: Convert the column back to use the new enum type
    op.execute("""
        ALTER TABLE core.requests
        ALTER COLUMN request_type TYPE core.requesttype
        USING request_type::TEXT::core.requesttype
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Create old enum with original (incorrect) uppercase values
    old_requesttype = postgresql.ENUM(
        "NAME",
        "EMAIL",
        "ADDRESS",
        "VACATE",
        name="requesttype_old",
        schema="core",
    )
    old_requesttype.create(op.get_bind(), checkfirst=True)

    # Alter column to VARCHAR temporarily
    op.execute("""
        ALTER TABLE core.requests
        ALTER COLUMN request_type TYPE VARCHAR
        USING request_type::TEXT
    """)

    # Drop the new enum type
    op.execute("DROP TYPE IF EXISTS core.requesttype CASCADE")

    # Rename old enum to the original name
    op.execute("ALTER TYPE core.requesttype_old RENAME TO requesttype")

    # Convert column back to use the old enum type
    op.execute("""
        ALTER TABLE core.requests
        ALTER COLUMN request_type TYPE core.requesttype
        USING request_type::TEXT::core.requesttype
    """)
