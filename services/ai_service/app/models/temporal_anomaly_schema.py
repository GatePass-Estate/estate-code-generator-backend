"""Pydantic request/response models for temporal (Matrix Profile) anomaly detection."""

from __future__ import annotations

from pydantic import UUID4, BaseModel, Field

from app.domain.scopes import TriggerMode


class TemporalAnalyzeRequest(BaseModel):
    """
    Estate-scoped request for the temporal endpoint.

    Not tied to a single validation: the analysis runs over the estate's entire
    log history. ``trigger`` is metadata only for now.
    """

    estate_id: UUID4
    trigger: TriggerMode = TriggerMode.REALTIME


class TemporalMatrixProfileDetail(BaseModel):
    """Matrix Profile diagnostics for the scored (latest) subsequence."""

    computed: bool = Field(
        ...,
        description=(
            "False when history was long enough but too flat (fewer than two "
            "non-empty days); score is then 0.0 and is_anomalous is false."
        ),
    )
    window_size_days: int
    series_length_days: int
    latest_window_index: int
    latest_profile_value: float
    profile_mean: float
    profile_max: float
    discord_index: int
    note: str | None = None


class TemporalAnalyzeResponse(BaseModel):
    """API response for ``POST /temporal-anomaly/analyze/{anomaly_type}``."""

    anomaly_type: str
    final_score: float
    is_anomalous: bool = Field(
        ...,
        description=(
            "True when the latest-subsequence discord score meets the "
            "configured temporal anomaly threshold."
        ),
    )
    explanation: str
    included_logs: list[str] = Field(
        default_factory=list,
        description="Which log tables fed the series (visitor_log/resident_log).",
    )
    detail: TemporalMatrixProfileDetail
