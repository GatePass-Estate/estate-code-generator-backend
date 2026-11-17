"""
Offline helpers for spatial anomaly finetuning (Phase 1 harness).

Supports replay metrics and synthetic perturbation without HTTP. Used by
``scripts/eval_spatial_anomaly.py`` and unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope
from app.pipeline.analysis_manager import (
    ScopeEnsembleContext,
    score_from_model_outputs,
    weighted_ensemble_score,
)
from app.pipeline.feature_contributions import compute_feature_contributions
from app.pipeline.spatial_anomaly_models.preprocess import (
    build_processed_block,
)


@dataclass(frozen=True)
class ScopeEvalRow:
    """One scope's scoring row for CSV/JSON export."""

    scope: str
    score: float
    matched: int
    eligible: int
    history_confidence: float
    effective_weight: float
    kmeans: float
    dbscan: float
    lof: float


def evaluate_scope_row(
    scope: AnalysisScope,
    *,
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
    model_outputs: dict[str, float],
    eligible_count: int,
    anomaly_type: AnomalyType = AnomalyType.VISITOR,
) -> ScopeEvalRow:
    """Build a :class:`ScopeEvalRow` from detector outputs and cohort counts."""
    matched = int(model_outputs.get("historical_reference_count", 0))
    score = score_from_model_outputs(model_outputs)
    ctx = ScopeEnsembleContext(
        scope=scope,
        score=score,
        matched_count=matched,
        eligible_count=eligible_count,
        anomaly_type=anomaly_type,
    )
    return ScopeEvalRow(
        scope=scope.value,
        score=score,
        matched=matched,
        eligible=eligible_count,
        history_confidence=ctx.history_confidence,
        effective_weight=ctx.effective_weight,
        kmeans=float(model_outputs.get("kmeans", 0.0)),
        dbscan=float(model_outputs.get("dbscan", 0.0)),
        lof=float(model_outputs.get("lof", 0.0)),
    )


def final_score_from_contexts(contexts: list[ScopeEnsembleContext]) -> float:
    """History-confidence weighted final score."""
    return weighted_ensemble_score(contexts)


def is_anomalous(final_score: float) -> bool:
    """Apply configured ensemble threshold."""
    return final_score >= settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD


def perturb_features(
    features: dict[str, float],
    overrides: dict[str, float],
) -> dict[str, float]:
    """Return a copy of ``features`` with ``overrides`` applied."""
    out = dict(features)
    out.update(overrides)
    return out


def scaled_focal_vector(
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
) -> dict[str, float]:
    """Focal values in the same scaled basis as detectors (for debugging)."""
    block = build_processed_block(focal_features, historical_features)
    return {
        name: float(block.x_focal[i])
        for i, name in enumerate(block.feature_names)
    }


def feature_contribution_rows(
    scope: AnalysisScope,
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
    scope_score: float,
) -> list[dict[str, Any]]:
    """Thin wrapper around :func:`compute_feature_contributions`."""
    return compute_feature_contributions(
        scope, focal_features, historical_features, scope_score
    )
