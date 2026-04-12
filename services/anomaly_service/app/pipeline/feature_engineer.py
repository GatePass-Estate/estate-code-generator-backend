"""Feature engineering manager — DAG order and incremental updates go here."""

from typing import Any

from app.domain.scopes import AnalysisScope
from app.pipeline.anomaly_pipeline import AnomalyPipelineBase


async def build_feature_vector(
    pipeline: AnomalyPipelineBase,
    scope: AnalysisScope,
    cleaned_records: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, float]:
    return await pipeline.engineer_scope_features(
        scope, cleaned_records, context
    )
