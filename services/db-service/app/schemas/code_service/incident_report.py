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
    "IncidentCategory",
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
        description="Optional free-text label when taxonomy does not fit.",
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
    def _require_category_or_custom(self) -> CreateRequest:
        if not self.category and not self.custom_category:
            raise ValueError(
                "Provide at least one category enum value or custom_category."
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


class SearchRequest(BaseSearchRequest):
    """Filter incident reports (non-deleted)."""

    estate_id: UUID4 | None = Field(
        default=None,
        description="Restrict to one estate.",
    )
    reported_by_user_id: UUID4 | None = None

    category: IncidentCategory | None = Field(
        default=None,
        description=(
            "Match reports whose category array includes this enum value."
        ),
    )


class ListResponse(BaseListResponse):
    """Paginated incident list."""

    items: List[GetResponse] = Field(..., description="Matching incidents.")
