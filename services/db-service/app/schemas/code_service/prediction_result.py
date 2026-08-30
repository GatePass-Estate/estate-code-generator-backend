"""Schemas for prediction-result search and result-page overview."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    model_config,
)
from app.schemas.code_service.log_feature_engineering import PredictionType
from app.schemas.code_service.visitor_log import Gender


HIGH_RISK_SCORE = 0.8
MEDIUM_SCORE = 0.5
NORMAL_SAMPLE_FRACTION = 0.3


class Severity(StrEnum):
    """final_score band: low < 0.5, medium 0.5 to 0.8, high >= 0.8."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UserType(StrEnum):
    """Guest (visitor log) vs resident-side prediction row."""

    GUEST = "guest"
    RESIDENT = "resident"


class SearchRequest(BaseSearchRequest):
    """Filters for the prediction-result list; list fields are OR'd."""

    estate_id: UUID4 = Field(..., description="Estate to scope predictions.")
    severity: list[Severity] | None = Field(default=None)
    gender: list[Gender] | None = Field(default=None)
    user_type: list[UserType] | None = Field(default=None)
    sort_order: Literal["asc", "desc"] = Field(default="desc")
    is_anomalous: bool | None = Field(default=None)


class PredictionListItem(BaseModel):
    """One prediction row for the result-page list."""

    model_config = model_config

    id: UUID4
    created_at: datetime
    prediction_type: PredictionType
    user_type: UserType
    gender: Gender | None = None
    display_name: str | None = None
    final_score: float | None = None
    is_anomalous: bool | None = None
    severity: Severity | None = None
    anomaly_type: str | None = None

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        """Emit the prediction id as a string in JSON."""
        return str(value)


class ListResponse(BaseListResponse):
    """Paginated prediction-result search payload."""

    items: list[PredictionListItem] = Field(default_factory=list)


class OverviewRequest(BaseSearchRequest):
    """Estate and date window for the result-page overview SQL."""

    estate_id: UUID4 = Field(..., description="Estate to scope the overview.")


class OverviewResponse(BaseModel):
    """Raw counts, 30% non-anomalous sample, and period-max maps."""

    model_config = model_config

    estate_name: str
    state: str | None = None
    country: str | None = None
    total_guests: int = 0
    resident_count: int = 0
    security_count: int = 0
    total_anomalous_instances: int = 0
    total_high_risk_instances: int = 0
    total_anomalous_residents_instances: int = 0
    total_anomalous_visitors_instances: int = 0
    normal_sample: list[dict[str, Any]] = Field(default_factory=list)
    # max feature/scope values across all predictions in the window
    feature_max_values: dict[str, float] = Field(default_factory=dict)
    scope_max_scores: dict[str, float] = Field(default_factory=dict)
    scope_feature_max_values: dict[str, dict[str, float]] = Field(
        default_factory=dict
    )
