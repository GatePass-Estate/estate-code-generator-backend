"""Schemas for the incident-report result page."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import List

from pydantic import UUID4, BaseModel, Field, field_serializer, field_validator

from app.schemas.base import BaseListResponse, BaseSearchRequest, model_config
from app.schemas.user_profile.incident_report import (
    GetResponse,
    IncidentCategory,
)

_ALL = "all"


def _drop_all_filter(values: list[str] | str | None) -> list[str] | None:
    """Treat ``all`` as unfiltered; remaining values are lowercased."""
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    if not values:
        return None
    normalized = [str(v).strip().lower() for v in values if str(v).strip()]
    if not normalized or _ALL in normalized:
        return None
    return normalized


class ReporterUserType(StrEnum):
    """Reporter bucket used on the incident result page."""

    RESIDENT = "resident"
    SECURITY = "security"


class OverviewRequest(BaseModel):
    """Estate and date window for incident result-page demographics."""

    model_config = model_config

    estate_id: UUID4
    from_date: datetime | None = None
    to_date: datetime | None = None

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        """Emit the estate id as a string."""
        return str(value)


class OverviewResponse(BaseModel):
    """Estate identity and reporter-role counts for the result page."""

    model_config = model_config

    estate_name: str
    state: str | None = None
    country: str | None = None
    total_reports: int = 0
    resident_report_count: int = 0
    security_report_count: int = 0


class SearchRequest(BaseSearchRequest):
    """Filter incidents by estate window, categories, and reporter type."""

    estate_id: UUID4
    categories: list[IncidentCategory] | None = Field(default=None)
    user_types: list[ReporterUserType] | None = Field(default=None)

    @field_validator("categories", mode="before")
    @classmethod
    def _categories_allow_all(cls, value):
        """``all`` means every incident category."""
        remaining = _drop_all_filter(value)
        if remaining is None:
            return None
        return remaining

    @field_validator("user_types", mode="before")
    @classmethod
    def _user_types_allow_all(cls, value):
        """``all`` means every reporter type."""
        remaining = _drop_all_filter(value)
        if remaining is None:
            return None
        return remaining

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        """Emit the estate id as a string."""
        return str(value)


class ListItem(GetResponse):
    """Incident row plus the reporter's result-page user-type bucket."""

    reporter_user_type: ReporterUserType | None = None


class ListResponse(BaseListResponse):
    """Paginated incident list for the result page."""

    items: List[ListItem] = Field(default_factory=list)
