"""Per-anomaly-type scope base weights."""

import pytest

from app.core.ensemble_config import scope_base_weight
from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope
from app.pipeline.analysis_manager import (
    ScopeEnsembleContext,
    weighted_ensemble_score,
)


def test_resident_scan_boosts_resident_scope_base_weight():
    visitor_resident = scope_base_weight(
        AnalysisScope.RESIDENT, AnomalyType.VISITOR
    )
    resident_resident = scope_base_weight(
        AnalysisScope.RESIDENT, AnomalyType.RESIDENT
    )
    assert resident_resident > visitor_resident
    assert resident_resident == pytest.approx(0.35)
    assert visitor_resident == pytest.approx(0.15)


def test_visitor_scope_weight_only_on_visitor_scan():
    assert (
        scope_base_weight(AnalysisScope.VISITOR, AnomalyType.VISITOR) == 0.30
    )
    assert (
        scope_base_weight(AnalysisScope.VISITOR, AnomalyType.RESIDENT) == 1.0
    )


def test_resident_scan_ensemble_favours_resident_scope():
    """Same scores; resident scan weights resident lens more heavily."""
    shared = [
        (AnalysisScope.TEMPORAL, 0.2),
        (AnalysisScope.SECURITY, 0.8),
        (AnalysisScope.ESTATE_WIDE, 0.4),
    ]
    visitor_contexts = [
        ScopeEnsembleContext(
            scope=AnalysisScope.VISITOR,
            score=0.1,
            matched_count=10,
            eligible_count=10,
            anomaly_type=AnomalyType.VISITOR,
        ),
        *[
            ScopeEnsembleContext(
                scope=s,
                score=sc,
                matched_count=10,
                eligible_count=10,
                anomaly_type=AnomalyType.VISITOR,
            )
            for s, sc in shared
        ],
        ScopeEnsembleContext(
            scope=AnalysisScope.RESIDENT,
            score=0.9,
            matched_count=10,
            eligible_count=10,
            anomaly_type=AnomalyType.VISITOR,
        ),
    ]
    resident_contexts = [
        *[
            ScopeEnsembleContext(
                scope=s,
                score=sc,
                matched_count=10,
                eligible_count=10,
                anomaly_type=AnomalyType.RESIDENT,
            )
            for s, sc in shared
        ],
        ScopeEnsembleContext(
            scope=AnalysisScope.RESIDENT,
            score=0.9,
            matched_count=10,
            eligible_count=10,
            anomaly_type=AnomalyType.RESIDENT,
        ),
    ]
    visitor_final = weighted_ensemble_score(visitor_contexts)
    resident_final = weighted_ensemble_score(resident_contexts)
    assert resident_final > visitor_final
