"""Ensemble of per-model scores (K-means, DBSCAN, LOF) with history-aware weights."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.ensemble_config import detector_weight, scope_base_weight
from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope
from app.pipeline.spatial_anomaly_models import (
    DBSCANAnomalyModel,
    KMeansAnomalyModel,
    LOFAnomalyModel,
)

# Shared detector instances (each ``predict`` refits; safe to reuse).
_kmeans_model = KMeansAnomalyModel()
_dbscan_model = DBSCANAnomalyModel()
_lof_model = LOFAnomalyModel()

_DETECTOR_KEYS = ("kmeans", "dbscan", "lof")


@dataclass(frozen=True)
class ScopeEnsembleContext:
    """Per-scope inputs for history-confidence weighting."""

    scope: AnalysisScope
    score: float
    matched_count: int
    eligible_count: int
    excluded_schema_mismatch_count: int = 0
    anomaly_type: AnomalyType = AnomalyType.VISITOR

    @property
    def base_weight(self) -> float:
        return scope_base_weight(self.scope, self.anomaly_type)

    @property
    def history_confidence(self) -> float:
        return history_confidence(
            matched=self.matched_count,
            eligible=self.eligible_count,
        )

    @property
    def effective_weight(self) -> float:
        return self.base_weight * self.history_confidence


def history_confidence(*, matched: int, eligible: int) -> float:
    """
    Map stored reference depth to ``[0, 1]`` for ensemble down-weighting.

    Thin cohorts (new visitors, post-migration cold scopes) receive low
    confidence so DBSCAN/LOF spikes do not flag benign first visits.

    Uses:
    - ``coverage`` = matched / eligible prior logs in the 30-day slice
    - ``fullness`` = matched / min(eligible, EXPECTED_REFERENCE_CAP)
    """
    min_matched = int(settings.SPATIAL_MIN_MATCHED_TO_SCORE)
    if matched < min_matched:
        return 0.0

    cap = max(1, int(settings.SPATIAL_EXPECTED_REFERENCE_CAP))
    elig = max(0, eligible)
    match = max(0, matched)

    coverage = match / max(1, elig)
    fullness = match / max(1, min(elig, cap) if elig > 0 else cap)
    raw = min(coverage, fullness)

    floor = float(settings.SPATIAL_HISTORY_CONFIDENCE_FLOOR)
    return float(max(0.0, min(1.0, floor + (1.0 - floor) * raw)))


async def ensemble_score(per_scope_scores: list[float]) -> float:
    """
    Legacy unweighted mean (tests and callers passing bare score lists).

    Prefer :func:`weighted_ensemble_score` for production orchestration.
    """
    if not per_scope_scores:
        return 0.0
    return sum(per_scope_scores) / len(per_scope_scores)


def weighted_ensemble_score(contexts: list[ScopeEnsembleContext]) -> float:
    """
    History-confidence weighted mean of per-scope scores.

    Scopes with ``history_confidence=0`` are excluded. When every scope is
    excluded, returns ``0.0`` (not anomalous by default).
    """
    num = 0.0
    den = 0.0
    for ctx in contexts:
        w = ctx.effective_weight
        if w <= 0.0:
            continue
        num += ctx.score * w
        den += w
    if den <= 0.0:
        return 0.0
    return float(num / den)


async def run_models(
    *,
    scope: AnalysisScope,
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
) -> dict[str, float]:
    """
    Run K-means, DBSCAN, and LOF detectors on aligned feature matrices.

    Returns:
        Dict with ``kmeans``, ``dbscan``, ``lof``, and
        ``historical_reference_count``.
    """
    k_block = _kmeans_model.process(focal_features, historical_features)
    d_block = _dbscan_model.process(focal_features, historical_features)
    l_block = _lof_model.process(focal_features, historical_features)
    k_score = _kmeans_model.predict(k_block)
    d_score = _dbscan_model.predict(d_block)
    l_score = _lof_model.predict(l_block)
    return {
        "kmeans": float(k_score),
        "dbscan": float(d_score),
        "lof": float(l_score),
        "historical_reference_count": float(len(historical_features)),
    }


def score_from_model_outputs(model_outputs: dict[str, float]) -> float:
    """
    Collapse detector outputs to one score in ``[0, 1]`` using configured weights.
    """
    num = 0.0
    den = 0.0
    for key in _DETECTOR_KEYS:
        raw = model_outputs.get(key)
        if raw is None:
            continue
        w = detector_weight(key)
        num += float(raw) * w
        den += w
    if den <= 0.0:
        return 0.0
    return float(num / den)
