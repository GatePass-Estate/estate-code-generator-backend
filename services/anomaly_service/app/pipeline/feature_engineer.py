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
    """
    Compute the feature vector for one ``AnalysisScope`` via the pipeline.

    ``cleaned_records`` must be the wrangled per-scope slice for ``scope`` from
    ``LogHistorySlices.rows_for_analysis_scope`` (wrangling runs inside
    ``load_log_records_for_analysis`` before the split).

    Delegates to ``AnomalyPipelineBase.engineer_scope_features`` so visitor vs
    resident behaviour stays encapsulated on the pipeline instance.
    """
    return await pipeline.engineer_scope_features(
        scope, cleaned_records, context
    )
