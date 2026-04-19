"""Resolves feature scopes for a pipeline (config-driven, internal-only)."""

from app.domain.scopes import AnalysisScope
from app.pipeline.anomaly_pipeline import AnomalyPipelineBase


def resolve_scopes_for_pipeline(
    pipeline: AnomalyPipelineBase,
) -> list[AnalysisScope]:
    """
    Return the ordered list of analysis scopes for the pipeline's anomaly type.

    Scopes are defined in ``app.core.scope_config`` (not client-overridable).
    """
    return pipeline.allowed_feature_scopes()
