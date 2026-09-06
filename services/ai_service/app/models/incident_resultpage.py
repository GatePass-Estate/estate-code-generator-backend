"""Response models for the incident-report summary result page."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ReporterUserType(StrEnum):
    """Reporter bucket: resident covers every role except security/guest/root."""

    RESIDENT = "resident"
    SECURITY = "security"


class RatioShare(BaseModel):
    """Headcount and share of resident + security reports."""

    count: int
    percentage: float = Field(
        ..., description="Share of resident + security reports, 0-100."
    )


class IncidentDemographic(BaseModel):
    """Estate identity, total reports, and reporter-role mix."""

    estate_name: str
    state: str | None = None
    country: str | None = None
    total_reports: int = 0
    ratio: dict[str, RatioShare] = Field(
        ...,
        description="Resident / security counts and percentages.",
    )


class CategoryEdaItem(BaseModel):
    """Peak time, share, and two snippets for one category."""

    category: str
    peak_time: Literal["morning", "afternoon", "evening_night"]
    incident_count: int
    percentage_share: float
    sample_reports: list[str] = Field(default_factory=list)


class CategoryEdaSection(BaseModel):
    """Top five categories as fields; the rest grouped by count desc."""

    top_1: CategoryEdaItem | None = None
    top_2: CategoryEdaItem | None = None
    top_3: CategoryEdaItem | None = None
    top_4: CategoryEdaItem | None = None
    top_5: CategoryEdaItem | None = None
    other_categories: dict[str, CategoryEdaItem] = Field(default_factory=dict)


class IncidentOverviewEda(BaseModel):
    """Existing cohort stats plus ranked category EDA and trends."""

    stats: dict = Field(default_factory=dict)
    categories: CategoryEdaSection = Field(default_factory=CategoryEdaSection)
    trends_detected: str = ""


class IncidentOverviewResponse(BaseModel):
    """Public overview payload: demographic, EDA, and cache flags."""

    demographic: IncidentDemographic
    eda: IncidentOverviewEda
    has_tier1_summary: bool = False
    has_tier2_summary: bool = False


class IncidentListItem(BaseModel):
    """One incident row for the result-page list."""

    id: str
    created_at: datetime
    occurred_at: datetime | None = None
    title: str | None = None
    category: list[str] = Field(default_factory=list)
    custom_category: str | None = None
    narrative: str
    reporter_user_type: ReporterUserType | None = None


class IncidentListResponse(BaseModel):
    """Paginated incident list for the result page."""

    items: list[IncidentListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 10


class IncidentInhouseSummary(BaseModel):
    """Topic-modelling report plus the shared category EDA."""

    executive_summary: str
    detailed_insight: str
    category_eda: CategoryEdaSection = Field(
        default_factory=CategoryEdaSection
    )
    topics: dict = Field(
        default_factory=dict,
        description="TF-IDF/NMF topic-modelling payload for the date window.",
    )


class IncidentLlmSummary(BaseModel):
    """LLM / heuristic narrative plus the same category EDA as tier 1."""

    executive_summary: str = ""
    key_patterns: list[str] = Field(default_factory=list)
    severity_assessment: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    data_limitations: str = ""
    category_eda: CategoryEdaSection = Field(
        default_factory=CategoryEdaSection
    )


class IncidentSummaryResponse(BaseModel):
    """Entitlement-gated summaries; withheld tiers are null."""

    entitled_tier: Literal["tier1", "tier2"]
    from_cache: bool = False
    tier1: IncidentInhouseSummary | None = None
    tier2: IncidentLlmSummary | None = None
