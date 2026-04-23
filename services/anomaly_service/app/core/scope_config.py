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
    """
    Return the ordered analysis scopes to run for ``anomaly_type``.

    Visitor pipelines include all scopes; resident pipelines omit the
    visitor-specific lens. Values come from static ``_DEFAULT_SCOPES``.
    """
    return list(_DEFAULT_SCOPES[anomaly_type])
