"""Pydantic request/response models for the anomaly service API."""

from typing import Any

from pydantic import BaseModel, Field

from app.domain.scopes import AnalysisScope, TriggerMode


class AnalyzeRequest(BaseModel):
    """Minimal contract for a first analysis call."""

    trigger: TriggerMode = TriggerMode.BATCH
    raw_visit_records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Stub; later from DB or Pub/Sub.",
    )
    scopes: list[AnalysisScope] | None = Field(
        default=None,
        description="Omitted → visitor scope.",
    )
    context: dict[str, Any] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    final_score: float
    per_scope_scores: dict[str, float]
    explanation: str
    scopes_evaluated: list[str]
