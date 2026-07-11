"""Ensemble of per-model scores (K-means, DBSCAN, LOF)."""

from __future__ import annotations

from app.domain.scopes import AnalysisScope
from app.pipeline.anomaly_models import (
    DBSCANAnomalyModel,
    KMeansAnomalyModel,
    LOFAnomalyModel,
)

# Shared detector instances (each ``predict`` refits; safe to reuse).
_kmeans_model = KMeansAnomalyModel()
_dbscan_model = DBSCANAnomalyModel()
_lof_model = LOFAnomalyModel()


async def ensemble_score(per_scope_scores: list[float]) -> float:
    """
    Combine per-scope scalar scores with an unweighted mean.

    Empty input returns ``0.0``. Used as the draft global score until a weighted
    or learned ensemble is configured.
    """
    if not per_scope_scores:
        return 0.0
    return sum(per_scope_scores) / len(per_scope_scores)


async def run_models(
    *,
    scope: AnalysisScope,
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
) -> dict[str, float]:
    """
    Run K-means, DBSCAN, and LOF detectors on aligned feature matrices.

    ``historical_features`` are prior engineered vectors for the same scope;
    each model runs ``process`` then ``predict`` on its own pipeline.

    Args:
        scope: Active analysis scope (reserved for future scope-aware models).
        focal_features: Engineered feature dict for the anchor validation.
        historical_features: Same keys as cohort rows loaded from the feature store.

    Returns:
        Dict with ``kmeans``, ``dbscan``, ``lof``, and
        ``historical_reference_count`` (length of ``historical_features``).
    """
    _ = scope
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
    Collapse detector outputs to one score in ``[0, 1]``.

    Uses the simple mean of ``kmeans``, ``dbscan``, and ``lof`` when present.
    Non-detector metadata (e.g. ``historical_reference_count``) is ignored.
    """
    detector_keys = ("kmeans", "dbscan", "lof")
    vals: list[float] = []
    for key in detector_keys:
        raw = model_outputs.get(key)
        if raw is None:
            continue
        vals.append(float(raw))
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))
