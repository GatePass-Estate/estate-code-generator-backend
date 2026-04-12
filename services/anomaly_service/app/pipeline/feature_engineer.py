"""Feature engineering manager — DAG order and incremental updates go here."""

from typing import Any

from app.pipeline.base import ScopeAnalysisBase


async def build_feature_vector(
    scope_impl: ScopeAnalysisBase,
    cleaned_records: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, float]:
    return await scope_impl.engineer_features(cleaned_records, context)
