"""Spatial anomaly eval harness helpers."""

import pytest

from app.domain.scopes import AnalysisScope
from app.pipeline.spatial_anomaly_eval import (
    evaluate_scope_row,
    final_score_from_contexts,
    perturb_features,
)
from app.pipeline.analysis_manager import ScopeEnsembleContext


def test_evaluate_scope_row_and_final_score():
    model_outputs = {
        "kmeans": 0.2,
        "dbscan": 0.2,
        "lof": 0.2,
        "historical_reference_count": 5.0,
    }
    row = evaluate_scope_row(
        AnalysisScope.TEMPORAL,
        focal_features={"hour_of_day": 9.0},
        historical_features=[{"hour_of_day": 8.0}] * 5,
        model_outputs=model_outputs,
        eligible_count=6,
    )
    assert row.matched == 5
    assert row.history_confidence > 0.0
    ctx = ScopeEnsembleContext(
        scope=AnalysisScope.TEMPORAL,
        score=row.score,
        matched_count=row.matched,
        eligible_count=row.eligible,
    )
    assert final_score_from_contexts([ctx]) == pytest.approx(row.score)


def test_perturb_features():
    base = {"a": 1.0, "b": 2.0}
    out = perturb_features(base, {"a": 99.0})
    assert out["a"] == 99.0
    assert out["b"] == 2.0
