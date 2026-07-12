"""Pydantic response models for spatial (feature-space) anomaly detection routes."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Re-exported for callers that historically imported these from this module.
from app.models.code_validation import (  # noqa: F401
    AnalyzeRequest,
    CodeValidationPayload,
    Receiver,
)


class FeatureContribution(BaseModel):
    """One engineered feature value for transparency payloads."""

    feature_name: str
    value: float
    weight: float | None = None
    contribution: float | None = None


class ScopeTransparencyDetail(BaseModel):
    """Per-scope score, engineered features, and per-detector outputs."""

    scope: str
    score: float
    feature_contributions: list[FeatureContribution]
    thresholds: dict[str, float] = Field(default_factory=dict)
    model_ids: list[str] = Field(default_factory=list)
    model_outputs: dict[str, float] = Field(default_factory=dict)


class AnalysisTransparency(BaseModel):
    """Structured transparency for audit and UI (scores, features, models)."""

    scopes: list[ScopeTransparencyDetail]
    ensemble_method: str
    ensemble_notes: str | None = None
    global_model_outputs: dict[str, float] = Field(default_factory=dict)


class SpatialAnalyzeResponse(BaseModel):
    """API response for ``POST /spatial-anomaly/analyze/{anomaly_type}``."""

    final_score: float
    per_scope_scores: dict[str, float]
    explanation: str
    scopes_evaluated: list[str]
    anomaly_type: str
    is_anomalous: bool = Field(
        ...,
        description=(
            "True when ensemble final_score meets the configured anomaly "
            "threshold (same flag persisted on the focal feature-store row)."
        ),
    )
    transparency: AnalysisTransparency
