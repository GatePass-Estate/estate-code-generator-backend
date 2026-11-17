"""History-confidence scope weighting (Phase 3a)."""

import pytest

from app.core.config import settings
from app.domain.scopes import AnalysisScope
from app.pipeline.analysis_manager import (
    ScopeEnsembleContext,
    history_confidence,
    weighted_ensemble_score,
)


def test_history_confidence_zero_when_matched_below_minimum():
    assert history_confidence(matched=0, eligible=5) == 0.0
    assert history_confidence(matched=1, eligible=5) == 0.0
    assert history_confidence(matched=4, eligible=20) == 0.0


def test_history_confidence_increases_with_matched_and_eligible():
    low = history_confidence(matched=5, eligible=20)
    high = history_confidence(matched=10, eligible=10)
    assert 0.0 < low < high <= 1.0


def test_weighted_ensemble_excludes_zero_confidence_scopes():
    contexts = [
        ScopeEnsembleContext(
            scope=AnalysisScope.VISITOR,
            score=1.0,
            matched_count=0,
            eligible_count=1,
        ),
        ScopeEnsembleContext(
            scope=AnalysisScope.TEMPORAL,
            score=0.4,
            matched_count=10,
            eligible_count=10,
        ),
    ]
    final = weighted_ensemble_score(contexts)
    assert final == pytest.approx(0.4)


def test_weighted_ensemble_all_zero_confidence_returns_zero():
    contexts = [
        ScopeEnsembleContext(
            scope=AnalysisScope.VISITOR,
            score=1.0,
            matched_count=0,
            eligible_count=0,
        ),
    ]
    assert weighted_ensemble_score(contexts) == 0.0


def test_new_visitor_thin_history_does_not_inflate_final_score():
    """Thin visitor/security scopes excluded; unweighted mean would still flag."""
    contexts = [
        ScopeEnsembleContext(
            scope=AnalysisScope.VISITOR,
            score=1.0,
            matched_count=0,
            eligible_count=1,
        ),
        ScopeEnsembleContext(
            scope=AnalysisScope.SECURITY,
            score=1.0,
            matched_count=1,
            eligible_count=5,
        ),
        ScopeEnsembleContext(
            scope=AnalysisScope.TEMPORAL,
            score=0.60,
            matched_count=8,
            eligible_count=8,
        ),
        ScopeEnsembleContext(
            scope=AnalysisScope.RESIDENT,
            score=0.55,
            matched_count=8,
            eligible_count=8,
        ),
        ScopeEnsembleContext(
            scope=AnalysisScope.ESTATE_WIDE,
            score=0.58,
            matched_count=8,
            eligible_count=8,
        ),
    ]
    unweighted = sum(c.score for c in contexts) / len(contexts)
    final = weighted_ensemble_score(contexts)
    assert unweighted >= settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
    assert final < settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
