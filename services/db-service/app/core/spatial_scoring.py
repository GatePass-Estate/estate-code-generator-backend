"""Spatial anomaly score thresholds shared with list/filter severity bands."""

from __future__ import annotations

from app.core.config import settings
from app.schemas.code_service.prediction_result import Severity


def medium_score_threshold() -> float:
    """Lower bound for medium severity (same as the anomalous threshold)."""
    return float(settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD)


def high_risk_score_threshold() -> float:
    """Lower bound for high severity."""
    return float(settings.SPATIAL_SEVERITY_HIGH_MIN)


def severity_from_final_score(score: float | None) -> Severity | None:
    """
    Map stored ``final_score`` onto low / medium / high.

    Low is strictly below :func:`medium_score_threshold`.
    """
    if score is None:
        return None
    if score >= high_risk_score_threshold():
        return Severity.HIGH
    if score >= medium_score_threshold():
        return Severity.MEDIUM
    return Severity.LOW
