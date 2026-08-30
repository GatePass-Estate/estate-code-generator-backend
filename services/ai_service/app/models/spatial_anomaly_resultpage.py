"""Response models for the spatial-anomaly result page."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(StrEnum):
    """final_score band: low < 0.5, medium 0.5 to 0.8, high >= 0.8."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UserType(StrEnum):
    """Guest (visitor log) vs resident-side prediction row."""

    GUEST = "guest"
    RESIDENT = "resident"


class RatioShare(BaseModel):
    """Headcount and share of guest + resident + security."""

    count: int
    percentage: float = Field(
        ..., description="Share of guest + resident + security, 0-100."
    )


class Demographic(BaseModel):
    """Estate identity, user mix, and anomalous/high-risk instance counts."""

    estate_name: str
    state: str | None = None
    country: str | None = None
    total_users: int = Field(
        ...,
        description="Residents, admins, primary admins, plus unique guests.",
    )
    total_guests: int = Field(
        ..., description="Unique visitor-log names in the timeframe."
    )
    ratio: dict[str, RatioShare] = Field(
        ...,
        description="Guest / resident / security counts and percentages.",
    )
    total_anomalous_instances: int = 0
    total_high_risk_instances: int = 0


class EvidenceSummary(BaseModel):
    """Anomalous prediction rows split by resident vs visitor log."""

    total_anomalous_residents_instances: int = 0
    total_anomalous_visitors_instances: int = 0


class SubFactor(BaseModel):
    """One feature inside a contributing-factor scope."""

    feature_name: str
    description: str
    normal_value: float | None = None
    weight: float | None = None
    scale: float | None = None
    percentage: float | None = None


class ContributingFactor(BaseModel):
    """One analysis scope with averaged score and nested sub-factors."""

    name: str
    description: str
    normal_value: float | None = Field(
        default=None, description="Averaged scope score for normal behaviour."
    )
    weight: float | None = None
    scale: float | None = None
    percentage: float | None = None
    sub_factors: list[SubFactor] = Field(default_factory=list)


class SpiderPlotPoint(BaseModel):
    """One ranked feature for the spider plot / top-factors list."""

    feature_name: str
    description: str
    weight: float | None = None
    normal_value: float | None = None
    scale: float | None = None
    percentage: float | None = None


class AnomalyOverview(BaseModel):
    """Spider plot, top six factors, and nested contributing factors."""

    spider_plot: list[SpiderPlotPoint] = Field(default_factory=list)
    top_contributing_factors: list[SpiderPlotPoint] = Field(
        default_factory=list
    )
    contributing_factors: list[ContributingFactor] = Field(
        default_factory=list
    )


class ResultPageOverviewResponse(BaseModel):
    """Public overview payload: demographic, evidence, anomaly overview."""

    demographic: Demographic
    evidence_summary: EvidenceSummary
    anomaly_overview: AnomalyOverview


class PredictionListItem(BaseModel):
    """One prediction row for the result-page list."""

    id: str
    created_at: datetime
    prediction_type: str
    user_type: UserType
    gender: str | None = None
    display_name: str | None = None
    final_score: float | None = None
    is_anomalous: bool | None = None
    severity: Severity | None = None
    anomaly_type: str | None = None


class PredictionListResponse(BaseModel):
    """Paginated prediction list with the requested sort order."""

    items: list[PredictionListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 10
    sort_order: Literal["asc", "desc"] = "desc"
