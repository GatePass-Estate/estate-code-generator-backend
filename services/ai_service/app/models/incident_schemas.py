"""Request / response models for incident topic modelling and summarisation API."""

from __future__ import annotations

from datetime import datetime

from pydantic import UUID4, BaseModel, Field


class IncidentSummarizeRequest(BaseModel):
    """
    Filter an estate's incident cohort.

    ``POST /incident-reports/summarize`` always runs TF-IDF+NMF topics; the LLM
    summary block is included only when the estate has active payment.
    """

    estate_id: UUID4
    from_date: datetime | None = Field(
        default=None,
        description="Lower bound on ``created_at`` (db-service search).",
    )
    to_date: datetime | None = Field(
        default=None,
        description="Upper bound on ``created_at`` (db-service search).",
    )
    max_records: int = Field(
        default=500,
        ge=1,
        le=2000,
        description="Safety cap on rows pulled before EDA / LLM / topics.",
    )
    n_topics: int | None = Field(
        default=None,
        ge=2,
        le=12,
        description=(
            "NMF topic count; auto-chosen from cohort size when omitted."
        ),
    )


class IncidentStructuredSummary(BaseModel):
    """LLM (or heuristic) output schema exposed to clients."""

    executive_summary: str = ""
    key_patterns: list[str] = Field(default_factory=list)
    severity_assessment: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    data_limitations: str = ""


class IncidentSummarySection(BaseModel):
    """
    Narrative summary block (LLM/heuristic).

    Empty when the estate does not have active payment / premium access.
    """

    eda: dict = Field(default_factory=dict)
    structured_summary: IncidentStructuredSummary = Field(
        default_factory=IncidentStructuredSummary,
    )
    llm_model: str | None = None
    llm_used: bool = False


class IncidentTopicTerm(BaseModel):
    """Weighted term in a discovered topic."""

    term: str
    weight: float


class IncidentTopicExample(BaseModel):
    """Short example row attached to a discovered theme."""

    title: str | None = None
    narrative_snippet: str | None = None


class DiscoveredIncidentTopic(BaseModel):
    """One latent topic with interpretable terms and sample ids."""

    topic_id: int
    label: str
    display_name: str | None = None
    keywords: list[str] = Field(default_factory=list)
    share_percent: float = 0.0
    top_terms: list[IncidentTopicTerm]
    document_count: int
    sample_incident_ids: list[str] = Field(default_factory=list)
    example_incidents: list[IncidentTopicExample] = Field(default_factory=list)


class IncidentTopicAssignment(BaseModel):
    """Dominant topic assignment for one incident row."""

    incident_id: str | None = None
    topic_id: int
    weight: float


class HumanTopicTheme(BaseModel):
    """One theme in the operator-facing summary."""

    topic_id: int
    name: str | None = None
    incident_count: int = 0
    share_percent: float = 0.0
    keywords: list[str] = Field(default_factory=list)
    examples: list[IncidentTopicExample] = Field(default_factory=list)


class HumanTopicReport(BaseModel):
    """Structured human-readable topic discovery summary."""

    headline: str = ""
    themes: list[HumanTopicTheme] = Field(default_factory=list)
    timeline_summary: str = ""
    full_text: str = ""


class IncidentTopicsSection(BaseModel):
    """TF-IDF + NMF topic discovery (always populated when rows exist)."""

    method: str = "tfidf_nmf"
    documents_modelled: int = 0
    n_topics: int = 0
    note: str | None = None
    topics: list[DiscoveredIncidentTopic] = Field(default_factory=list)
    assignments: list[IncidentTopicAssignment] = Field(default_factory=list)
    temporal_overview: dict = Field(default_factory=dict)
    human_report: HumanTopicReport | None = None
    report_text: str | None = None


class IncidentSummarizeResponse(BaseModel):
    """
    Combined incident intelligence response.

    ``topics`` is always filled when incidents exist. ``summary`` is only
    populated when ``estate_payment_active`` is true.
    """

    estate_id: str
    record_count: int
    estate_payment_active: bool = True
    summary: IncidentSummarySection = Field(
        default_factory=IncidentSummarySection,
    )
    topics: IncidentTopicsSection = Field(
        default_factory=IncidentTopicsSection
    )
