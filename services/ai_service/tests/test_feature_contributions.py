"""Feature-level weights and contributions (Phase 4)."""

import pytest

from app.domain import features as feat
from app.domain.scopes import AnalysisScope
from app.pipeline.feature_contributions import compute_feature_contributions


def test_feature_weights_sum_to_one_and_contributions_scale_with_scope_score():
    focal = {feat.HOUR_OF_DAY: 23.0, feat.NIGHT_VISIT_FLAG: 1.0}
    hist = [
        {feat.HOUR_OF_DAY: 9.0, feat.NIGHT_VISIT_FLAG: 0.0},
        {feat.HOUR_OF_DAY: 10.0, feat.NIGHT_VISIT_FLAG: 0.0},
        {feat.HOUR_OF_DAY: 8.0, feat.NIGHT_VISIT_FLAG: 0.0},
    ]
    rows = compute_feature_contributions(
        AnalysisScope.TEMPORAL,
        focal,
        hist,
        scope_score=0.8,
    )
    weights = [float(r["weight"]) for r in rows]
    assert sum(weights) == pytest.approx(1.0, abs=1e-5)
    for row in rows:
        assert float(row["contribution"]) == pytest.approx(
            float(row["weight"]) * 0.8, abs=1e-5
        )


def test_uniform_weights_when_no_history():
    focal = {feat.HOUR_OF_DAY: 12.0}
    rows = compute_feature_contributions(
        AnalysisScope.TEMPORAL,
        focal,
        [],
        scope_score=0.5,
    )
    assert len(rows) == 1
    assert float(rows[0]["weight"]) == pytest.approx(1.0)
