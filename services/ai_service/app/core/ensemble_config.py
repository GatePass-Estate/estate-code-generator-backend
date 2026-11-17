"""
Spatial anomaly ensemble weights (detector, scope, and feature transparency).

Three independent weight layers (finetuning Phase 3–4):

1. **Detector weights** (:data:`DETECTOR_WEIGHTS`) — collapse K-means, DBSCAN,
   and LOF into one per-scope score inside :func:`analysis_manager.score_from_model_outputs`.
2. **Scope base weights** (:data:`SCOPE_BASE_WEIGHTS_BY_ANOMALY_TYPE`) —
   prior importance of each behavioural lens *before* history depth is known.
   Multiplied at runtime by ``history_confidence`` (see
   :func:`analysis_manager.weighted_ensemble_score`). Estate-wide is
   intentionally low (noisy broad cohort).
3. **Feature priors** (:data:`_SCOPE_FEATURE_BASE_WEIGHTS`) — affect
   **transparency only** (spider plot / contribution ranking), not detector
   inputs. Night-activity features boosted; cadence features down-weighted.

Runtime knobs (threshold, min matched refs, confidence floor) live in
:mod:`app.core.config`. This file holds static priors tuned during the
finetuning session; swap or extend for estate-specific tables later.
"""

from __future__ import annotations

from app.domain import features as feat
from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope

# --- Per-detector collapse weights (Phase 3b) ---
DETECTOR_WEIGHTS: dict[str, float] = {
    "kmeans": 0.35,
    "dbscan": 0.30,
    "lof": 0.35,
}

# --- Base scope priors before history-confidence multiplier (Phase 3b) ---
# Visitor scan centres on visitor_specific; resident scan boosts resident_specific.
SCOPE_BASE_WEIGHTS_BY_ANOMALY_TYPE: dict[
    AnomalyType, dict[AnalysisScope, float]
] = {
    AnomalyType.VISITOR: {
        AnalysisScope.TEMPORAL: 0.20,
        AnalysisScope.VISITOR: 0.30,
        AnalysisScope.RESIDENT: 0.15,
        AnalysisScope.SECURITY: 0.15,
        AnalysisScope.ESTATE_WIDE: 0.10,
    },
    AnomalyType.RESIDENT: {
        AnalysisScope.TEMPORAL: 0.20,
        AnalysisScope.RESIDENT: 0.35,
        AnalysisScope.SECURITY: 0.15,
        AnalysisScope.ESTATE_WIDE: 0.12,
    },
}

# Back-compat alias for visitor pipeline defaults.
SCOPE_BASE_WEIGHTS: dict[AnalysisScope, float] = (
    SCOPE_BASE_WEIGHTS_BY_ANOMALY_TYPE[AnomalyType.VISITOR]
)

# --- Feature-level priors (Phase 4); default 1.0 when omitted ---
_DEFAULT_FEATURE_WEIGHT = 1.0

_SCOPE_FEATURE_BASE_WEIGHTS: dict[AnalysisScope, dict[str, float]] = {
    AnalysisScope.TEMPORAL: {
        feat.NIGHT_VISIT_FLAG: 1.8,
        feat.HOUR_OF_DAY: 1.2,
        feat.VISIT_HOUR_BUCKET: 1.1,
        feat.DAY_OF_WEEK: 1.0,
        feat.IS_WEEKEND: 1.0,
    },
    AnalysisScope.VISITOR: {
        feat.RELATIONSHIP_TRANSITION: 1.4,
        feat.VISIT_INTERARRIVAL_TIME: 0.6,
        feat.VISITOR_WEEKLY_FREQUENCY: 0.6,
    },
    AnalysisScope.RESIDENT: {
        feat.VISIT_INTERARRIVAL_TIME: 0.6,
        feat.RESIDENT_VISIT_FREQUENCY: 0.6,
    },
    AnalysisScope.SECURITY: {
        feat.GUARD_NIGHT_VALIDATION_FREQUENCY: 1.6,
        feat.GUARD_NIGHT_VALIDATION_SHARE: 1.7,
    },
    AnalysisScope.ESTATE_WIDE: {
        feat.GUARD_NIGHT_VALIDATION_SHARE: 1.5,
        feat.VISITOR_WEEKLY_FREQUENCY: 0.6,
        feat.RESIDENT_VISIT_FREQUENCY: 0.6,
        feat.VISIT_INTERARRIVAL_TIME: 0.6,
        feat.GUARD_NIGHT_VALIDATION_FREQUENCY: 1.4,
    },
}


def detector_weight(detector_key: str) -> float:
    """Return configured detector weight (``kmeans``, ``dbscan``, ``lof``)."""
    return float(DETECTOR_WEIGHTS.get(detector_key, 1.0))


def scope_base_weight(
    scope: AnalysisScope,
    anomaly_type: AnomalyType = AnomalyType.VISITOR,
) -> float:
    """Return base ensemble weight for ``scope`` before history confidence."""
    table = SCOPE_BASE_WEIGHTS_BY_ANOMALY_TYPE.get(
        anomaly_type,
        SCOPE_BASE_WEIGHTS_BY_ANOMALY_TYPE[AnomalyType.VISITOR],
    )
    return float(table.get(scope, 1.0))


def feature_base_weight(scope: AnalysisScope, feature_name: str) -> float:
    """Return configured feature prior for ``scope`` / ``feature_name``."""
    scope_map = _SCOPE_FEATURE_BASE_WEIGHTS.get(scope, {})
    return float(scope_map.get(feature_name, _DEFAULT_FEATURE_WEIGHT))
