"""Severity bands align with ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD."""

from app.core.config import settings
from app.core.severity_config import (
    severity_from_final_score,
    severity_label_from_final_score,
)
from app.models.spatial_anomaly_resultpage import Severity


def test_severity_low_below_threshold():
    threshold = settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
    assert severity_from_final_score(threshold - 0.01) == Severity.LOW
    assert severity_label_from_final_score(threshold - 0.01) == "low"


def test_severity_medium_at_threshold():
    threshold = settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
    high = settings.SPATIAL_SEVERITY_HIGH_MIN
    assert severity_from_final_score(threshold) == Severity.MEDIUM
    assert severity_from_final_score(high - 0.01) == Severity.MEDIUM


def test_severity_high_at_high_min():
    high = settings.SPATIAL_SEVERITY_HIGH_MIN
    assert severity_from_final_score(high) == Severity.HIGH
    assert severity_from_final_score(1.0) == Severity.HIGH


def test_severity_none_when_score_missing():
    assert severity_from_final_score(None) is None
    assert severity_label_from_final_score(None) == "unknown"


def test_medium_not_assigned_below_anomalous_threshold():
    """Scores that are not anomalous must not receive medium/high severity."""
    threshold = settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
    score = threshold - 0.05
    assert score < threshold
    assert severity_from_final_score(score) == Severity.LOW
