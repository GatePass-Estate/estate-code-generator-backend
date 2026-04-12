"""
Internal feature scopes per anomaly type (not client-configurable).

Loaded from static defaults; override via env JSON in a later iteration if
needed.
"""

from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope

_DEFAULT_SCOPES: dict[AnomalyType, tuple[AnalysisScope, ...]] = {
    AnomalyType.VISITOR: tuple(AnalysisScope),
    AnomalyType.RESIDENT: tuple(
        s for s in AnalysisScope if s != AnalysisScope.VISITOR
    ),
}


def scopes_for_anomaly_type(anomaly_type: AnomalyType) -> list[AnalysisScope]:
    """Ordered list of feature scopes to run for the given anomaly pipeline."""
    return list(_DEFAULT_SCOPES[anomaly_type])
