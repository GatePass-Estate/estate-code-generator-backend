from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import List

from pydantic import (
    UUID4,
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "CreateRequest",
    "CreateResponse",
    "GetResponse",
    "GetResponseWithReadStatus",
    "IncidentCategory",
    "ListResponseWithReadStatus",
    "MarkReadRequest",
    "MarkAllReadRequest",
    "ClearReadRequest",
    "ReporterDetails",
    "SearchRequest",
    "ListResponse",
]


class IncidentCategory(StrEnum):
    """Controlled incident taxonomy (stored as PostgreSQL enum array)."""

    SECURITY = "security"
    ACCESS_CONTROL = "access_control"
    NOISE_DISTURBANCE = "noise_disturbance"
    PROPERTY_DAMAGE = "property_damage"
    MAINTENANCE = "maintenance"
    FIRE_SAFETY = "fire_safety"
    MEDICAL_EMERGENCY = "medical_emergency"
    THEFT = "theft"
    HARASSMENT = "harassment"
    DISPUTE = "dispute"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    OTHER = "other"


class IncidentReportBase(BaseModel):
    """Shared incident fields."""

    estate_id: UUID4 = Field(
        ...,
        description="Estate this incident belongs to.",
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    reported_by_user_id: UUID4 | None = Field(
        default=None,
        description="User who filed the report, when known.",
    )

    @field_serializer("reported_by_user_id")
    def serialize_reported_by(self, value: UUID4 | None) -> str | None:
        return str(value) if value is not None else None

    title: str | None = Field(
        default=None,
        description="Optional short headline for the incident.",
    )
    category: list[IncidentCategory] = Field(
        default_factory=list,
        description="Zero or more taxonomy categories (enum values).",
    )
    custom_category: str | None = Field(
        default=None,
        description=("Optional free-text label when taxonomy does not fit."),
    )
    narrative: str = Field(..., description="Free-text description.")
    occurred_at: datetime = Field(
        ...,
        description="When the incident occurred (timezone-aware).",
    )

    model_config = model_config

    @field_validator("title", "custom_category", mode="before")
    @classmethod
    def _strip_optional_strings(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_categories(cls, v: object) -> list[IncidentCategory]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("category must be a JSON array of enum values")
        out: list[IncidentCategory] = []
        for item in v:
            if isinstance(item, IncidentCategory):
                out.append(item)
            else:
                out.append(IncidentCategory(str(item).strip().lower()))
        return out


class CreateRequest(IncidentReportBase):
    """Create body for a new incident report."""

    @model_validator(mode="after")
    def _validate_category_exclusive(self) -> CreateRequest:
        has_category = bool(self.category)
        has_custom = bool(
            self.custom_category and self.custom_category.strip()
        )
        if not has_category and not has_custom:
            raise ValueError("Provide either a category or a custom_category.")
        if has_category and has_custom:
            raise ValueError(
                "Provide either a category or a custom_category," " not both."
            )
        return self


class CreateResponse(BaseModel):
    """Minimal payload after insert."""

    id: UUID4

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime
    model_config = model_config


class GetResponse(SharedModel, IncidentReportBase):
    """Full row for GET/search items."""


class ReporterDetails(BaseModel):
    """User details for the sender's panel."""

    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    home_address: str | None = None

    model_config = model_config


class GetResponseWithReadStatus(GetResponse):
    """GetResponse enriched with per-admin read status."""

    is_read: bool = False
    read_at: datetime | None = None
    reporter: ReporterDetails | None = None


class ListResponse(BaseListResponse):
    """Paginated incident list (no read status)."""

    items: List[GetResponse] = Field(..., description="Matching incidents.")


class ListResponseWithReadStatus(BaseListResponse):
    """Paginated incident list enriched with per-admin read status."""

    items: List[GetResponseWithReadStatus] = Field(
        ..., description="Matching incidents with read status."
    )


class SearchRequest(BaseSearchRequest):
    """Filter incident reports (non-deleted, non-cleared)."""

    estate_id: UUID4 | None = Field(
        default=None,
        description="Restrict to one estate.",
    )
    reported_by_user_id: UUID4 | None = None

    category: IncidentCategory | None = Field(
        default=None,
        description=(
            "Match reports whose category array includes this value."
        ),
    )


class MarkReadRequest(BaseModel):
    """Body for marking a single incident report as read."""

    admin_id: UUID4

    @field_serializer("admin_id")
    def serialize_admin_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class MarkAllReadRequest(BaseModel):
    """Body for bulk-marking all uncleared reports as read."""

    admin_id: UUID4
    estate_id: UUID4

    @field_serializer("admin_id")
    def serialize_admin_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class ClearReadRequest(BaseModel):
    """Body for soft-deleting all read records for an admin."""

    admin_id: UUID4
    estate_id: UUID4

    @field_serializer("admin_id")
    def serialize_admin_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config
