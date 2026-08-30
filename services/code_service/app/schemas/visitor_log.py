from datetime import datetime
from typing import List

from pydantic import UUID4, BaseModel, ConfigDict, Field

from app.schemas.code_service import Gender, Relation

__all__ = [
    "VisitorLogEntry",
    "ListResponse",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class VisitorLogEntry(BaseModel):
    """
    A single visitor-log entry returned by the BFF.

    Attributes:
        id (UUID): Unique identifier for the visitor log entry.
        created_at (DateTime): Earliest log row time on first-level unique
            history; validation log creation time otherwise.
        updated_at (DateTime): Time when the entry was last updated.
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relation): Relation to the resident.
        gender (Gender): Gender of the visitor.
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit.
        visit_time (DateTime): Timestamp of visitor validation.
        resident_fullname (str): Denormalized full name of the visited
            resident (``user_id``).
        usage_count (int): Total validations for this code; set on first-level
            unique history only.
        code_deleted (bool): Whether the visitor code is missing from cache
            or past ``valid_until``; set after history retrieval.
    """

    id: UUID4 = Field(..., description="Unique identifier for the log entry")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    user_id: UUID4 = Field(
        ..., description="Reference to the visited resident"
    )
    estate_id: UUID4 = Field(..., description="Reference to the estate")
    visitor_fullname: str = Field(..., description="Full name of the visitor")
    relationship_with_resident: Relation = Field(
        ..., description="Relation: family, partner, friend, delivery, etc"
    )
    gender: Gender = Field(
        ..., description="Gender: male, female, prefer_not_to_say"
    )
    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    security_id: UUID4 = Field(
        ..., description="Security personnel who validated the visit"
    )
    visit_time: datetime = Field(
        ..., description="Timestamp of visitor validation"
    )
    resident_fullname: str | None = Field(
        default=None, description="Full name of the visited resident (user_id)"
    )
    usage_count: int | None = Field(
        default=None,
        description="Total validations for this code (first-level only)",
    )
    code_deleted: bool | None = Field(
        default=None,
        description=(
            "Whether the visitor code is expired or no longer in cache"
        ),
    )

    model_config = model_config


class ListResponse(BaseModel):
    """
    Paginated visitor-log history ordered latest first.

    First-level (``/me``, ``/user``) returns one entry per unique
    ``hashed_code`` with ``usage_count``; ``created_at`` is the earliest log
    row per code (from db-service ``unique=true``). Second-level
    (``/me/{code}``, ``/user/{code}``) returns every visit for a single code.
    """

    total: int = Field(..., description="Total number of entries")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[VisitorLogEntry] = Field(
        ..., description="Ordered list of visitor log entries"
    )

    model_config = model_config
