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

    Validation rows always include ``security_id``. The synthetic code-
    creation row appended on code-level history (``/{code}`` endpoints) omits
    ``security_id`` and uses ``access_time`` equal to the access-code
    ``created_at``.

    Attributes:
        id (UUID): Unique identifier for the resident log entry.
        created_at (DateTime): Time when the entry was created.
        updated_at (DateTime): Time when the entry was last updated.
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access; null
            for the code-creation row on code-level history.
        access_time (DateTime): Timestamp of resident access validation or code
            creation when ``security_id`` is null.
        full_name (str): Denormalized full name of the resident (``user_id``).
    """

    id: UUID4 = Field(..., description="Unique identifier for the log entry")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    user_id: UUID4 = Field(..., description="Reference to the resident")
    estate_id: UUID4 = Field(..., description="Reference to the estate")
    hashed_code: str = Field(
        ..., description="Resident's generated access code"
    )
    security_id: UUID4 | None = Field(
        default=None,
        description="Security personnel who validated the access",
    )
    access_time: datetime = Field(
        ..., description="Timestamp of resident access validation"
    )
    full_name: str | None = Field(
        default=None, description="Full name of the resident (user_id)"
    )

    model_config = model_config


class ListResponse(BaseModel):
    """
    Paginated first-level resident access history (``/me``, ``/user``).

    Returns one entry per unique ``hashed_code``, ordered latest first.
    Does not include ``code_deleted``; use :class:`CodeHistoryListResponse`
    for code-level drill-down.
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

    Extends :class:`ListResponse` with ``code_deleted``, which reflects
    whether the earliest access-code row for the requested ``hashed_code`` is
    soft-deleted. When the current page covers the chronologically earliest
    slot in the latest-first timeline, the access-code creation row is
    appended as the last item (``security_id`` is null on that row).
    """

    code_deleted: bool = Field(
        ...,
        description=(
            "True when the earliest access-code row for this code is deleted"
        ),
    )

    model_config = model_config
