"""
Map spatial ``final_score`` to severity bands aligned with the anomaly threshold.

Severity bands mirror ai-service and db-service so result pages and stored
predictions stay consistent after finetuning (threshold 0.74, high at 0.80).
"""

from __future__ import annotations

from app.core.config import settings
from app.models.spatial_anomaly_resultpage import Severity


def severity_from_final_score(score: float | None) -> Severity | None:
    """
    Map ``final_score`` onto low / medium / high.

    Bands align with :attr:`settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD`:
    - low: below threshold (not anomalous)
    - medium: threshold <= score < high min (anomalous, moderate)
    - high: score >= high min
    """
    if score is None:
        return None
    threshold = float(settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD)
    high = float(settings.SPATIAL_SEVERITY_HIGH_MIN)
    if score >= high:
        return Severity.HIGH
    if score >= threshold:
        return Severity.MEDIUM
    return Severity.LOW


def severity_label_from_final_score(score: float | None) -> str:
    """Human-readable severity label; ``unknown`` when score is missing."""
    severity = severity_from_final_score(score)
    return severity.value if severity is not None else "unknown"
