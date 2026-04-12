"""Resolves feature scopes for a pipeline (config-driven, internal-only)."""

from app.domain.scopes import AnalysisScope
from app.pipeline.anomaly_pipeline import AnomalyPipelineBase


def resolve_scopes_for_pipeline(
    pipeline: AnomalyPipelineBase,
) -> list[AnalysisScope]:
    """Return scopes configured for this anomaly type (see scope_config)."""
    return pipeline.allowed_feature_scopes()
