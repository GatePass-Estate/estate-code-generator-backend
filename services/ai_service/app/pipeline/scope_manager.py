"""Resolves feature scopes for a pipeline (config-driven, internal-only)."""

from app.domain.scopes import AnalysisScope
from app.pipeline.spatial_anomaly_pipeline import SpatialAnomalyPipelineBase


def resolve_scopes_for_pipeline(
    pipeline: SpatialAnomalyPipelineBase,
) -> list[AnalysisScope]:
    """
    Return the ordered list of analysis scopes for the pipeline's anomaly type.

    Scopes are defined in ``app.core.scope_config`` (not client-overridable).
    """
    return pipeline.allowed_feature_scopes()
