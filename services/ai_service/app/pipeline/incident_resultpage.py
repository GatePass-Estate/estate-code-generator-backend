"""Map db-service payloads and build in-house incident summaries."""

from __future__ import annotations

from typing import Any

from app.models.incident_resultpage import (
    CategoryEdaSection,
    IncidentDemographic,
    IncidentInhouseSummary,
    IncidentLlmSummary,
    IncidentOverviewEda,
    IncidentOverviewResponse,
    RatioShare,
)
from app.pipeline.incident_eda import (
    build_category_eda,
    build_incident_eda,
    format_incident_trends,
)
from app.pipeline.incident_topic_modelling import discover_incident_topics


def _pct(count: int, total: int) -> float:
    """
    Return ``count / total * 100`` rounded, or 0 when total is 0.

    Arguments:
        count: Numerator headcount.
        total: Denominator headcount.

    Returns:
        A percentage in ``0..100``, rounded to two decimals.
    """
    if total <= 0:
        return 0.0
    return round((count / total) * 100.0, 2)


def category_eda_from_records(
    records: list[dict[str, Any]],
) -> CategoryEdaSection:
    """
    Validate ranked category EDA built from incident rows.

    Arguments:
        records: Incident rows in the requested window.

    Returns:
        A ``CategoryEdaSection`` (fixed taxonomy only).
    """
    return CategoryEdaSection.model_validate(build_category_eda(records))


def overview_from_parts(
    *,
    db_overview: dict[str, Any],
    records: list[dict[str, Any]],
    has_tier1_summary: bool = False,
    has_tier2_summary: bool = False,
) -> IncidentOverviewResponse:
    """
    Combine db-service counts with Python EDA for the overview.

    Resident share is every reporter role except security, guest, and
    root. Percentages are of resident + security reports, not of
    ``total_reports`` (unknown / excluded roles sit outside the ratio).
    Cache flags report whether each summary tier is already stored
    for this estate and date window.

    Arguments:
        db_overview: Estate identity and reporter-role counts.
        records: Incident rows used for EDA and trends.
        has_tier1_summary: In-house payload already cached.
        has_tier2_summary: LLM payload already cached.

    Returns:
        The public overview payload.
    """
    resident = int(db_overview.get("resident_report_count") or 0)
    security = int(db_overview.get("security_report_count") or 0)
    mix = resident + security
    stats = build_incident_eda(records)
    categories = category_eda_from_records(records)
    trends = format_incident_trends(
        record_count=int(db_overview.get("total_reports") or len(records)),
        category_eda=categories.model_dump(),
        stats=stats,
    )
    return IncidentOverviewResponse(
        demographic=IncidentDemographic(
            estate_name=str(db_overview.get("estate_name") or ""),
            state=db_overview.get("state"),
            country=db_overview.get("country"),
            total_reports=int(db_overview.get("total_reports") or 0),
            ratio={
                "resident": RatioShare(
                    count=resident, percentage=_pct(resident, mix)
                ),
                "security": RatioShare(
                    count=security, percentage=_pct(security, mix)
                ),
            },
        ),
        eda=IncidentOverviewEda(
            stats=stats,
            categories=categories,
            trends_detected=trends,
        ),
        has_tier1_summary=has_tier1_summary,
        has_tier2_summary=has_tier2_summary,
    )


def build_inhouse_incident_summary(
    records: list[dict[str, Any]],
    *,
    n_topics: int | None = None,
) -> IncidentInhouseSummary:
    """
    Run TF-IDF/NMF topic modelling for the date-window cohort.

    No LLM call. Uses the same category EDA that is attached to tier 2.

    Arguments:
        records: Incident rows in the date window.
        n_topics: Optional NMF topic count override.

    Returns:
        Executive summary, detailed insight, shared category EDA,
        and the topic-modelling payload.
    """
    modelled = discover_incident_topics(records, n_topics=n_topics)
    categories = category_eda_from_records(records)
    human = modelled.get("human_report") or {}
    if not isinstance(human, dict):
        human = {}
    report_text = str(
        modelled.get("report_text") or human.get("full_text") or ""
    )
    headline = str(human.get("headline") or "").strip()
    return IncidentInhouseSummary(
        executive_summary=headline or report_text,
        detailed_insight=report_text,
        category_eda=categories,
        topics=modelled if isinstance(modelled, dict) else {},
    )


def attach_category_eda(
    llm: IncidentLlmSummary,
    categories: CategoryEdaSection,
) -> IncidentLlmSummary:
    """
    Copy the shared category EDA onto a generated LLM summary.

    Arguments:
        llm: Validated LLM / heuristic narrative.
        categories: Category EDA already built for tier 1.

    Returns:
        A copy of ``llm`` with ``category_eda`` replaced.
    """
    return llm.model_copy(update={"category_eda": categories})
