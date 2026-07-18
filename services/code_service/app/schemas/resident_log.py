from datetime import datetime
from typing import List

from pydantic import UUID4, BaseModel, ConfigDict, Field

__all__ = [
    "ResidentLogEntry",
    "ListResponse",
    "CodeHistoryListResponse",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class ResidentLogEntry(BaseModel):
    """
    A single resident access-log entry returned by the BFF.

    Attributes:
        id (UUID): Unique identifier for the resident log entry.
        created_at (DateTime): Access-code generation time on first-level
            unique history; validation log creation time otherwise.
        updated_at (DateTime): Time when the entry was last updated.
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access.
        access_time (DateTime): Timestamp of resident access validation.
        full_name (str): Denormalized full name of the resident (``user_id``).
        usage_count (int): Total validations for this code; set on first-level
            unique history only.
        code_deleted (bool): Whether the resident access code is soft-deleted;
            set on first-level unique history only.
    """

    id: UUID4 = Field(..., description="Unique identifier for the log entry")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    user_id: UUID4 = Field(..., description="Reference to the resident")
    estate_id: UUID4 = Field(..., description="Reference to the estate")
    hashed_code: str = Field(
        ..., description="Resident's generated access code"
    )
    security_id: UUID4 = Field(
        ..., description="Security personnel who validated the access"
    )
    access_time: datetime = Field(
        ..., description="Timestamp of resident access validation"
    )
    full_name: str | None = Field(
        default=None, description="Full name of the resident (user_id)"
    )
    usage_count: int | None = Field(
        default=None,
        description="Total validations for this code (first-level only)",
    )
    code_deleted: bool | None = Field(
        default=None,
        description=(
            "Whether the resident access code is soft-deleted (first-level)"
        ),
    )

    model_config = model_config


class ListResponse(BaseModel):
    """
    Paginated first-level resident access history (``/me``, ``/user``).

    Returns one entry per unique ``hashed_code`` with ``usage_count`` and
    ``code_deleted``, ordered latest first. ``created_at`` on each item is the
    access-code generation time from ``accesscode/search``.
    """

    total: int = Field(..., description="Total number of entries")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[ResidentLogEntry] = Field(
        ..., description="Ordered list of resident log entries"
    )

    model_config = model_config


class CodeHistoryListResponse(ListResponse):
    """
    Paginated code-level resident access history (``/me/{code}``,
    ``/user/{code}``).

    ``items`` are validation events only (latest first). Code lifecycle
    metadata (``code_created_at``, ``code_deleted_at``, ``code_deleted``)
    comes from the access-code row, not from ``items``.
    """

    code_deleted: bool = Field(
        ...,
        description=(
            "True when the access-code row for this code is soft-deleted"
        ),
    )
    code_created_at: datetime | None = Field(
        default=None,
        description="When the access code was generated",
    )
    code_deleted_at: datetime | None = Field(
        default=None,
        description="When the access code became inactive (if deleted)",
    )

    model_config = model_config
