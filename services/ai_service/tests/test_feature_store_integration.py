"""Helpers for loading historical engineered vectors from db-service."""

from app.domain.log_feature_store import (
    historical_vectors_for_scope,
    previous_anchor_log_ids,
)
from app.domain.scopes import AnalysisScope


def test_historical_vectors_for_scope_reads_matching_json_column():
    rows = [
        {
            "features_visitor_specific": {"hour_of_day": 14.0},
            "features_resident_specific": {"hour_of_day": 9.0},
        }
    ]
    assert historical_vectors_for_scope(rows, AnalysisScope.VISITOR) == [
        {"hour_of_day": 14.0}
    ]
    assert historical_vectors_for_scope(rows, AnalysisScope.RESIDENT) == [
        {"hour_of_day": 9.0}
    ]


def test_previous_anchor_log_ids_excludes_focal():
    import uuid

    a = uuid.uuid4()
    b = uuid.uuid4()
    focal = {"id": str(b)}
    scope_rows = [{"id": str(a)}, {"id": str(b)}, {"id": None}]
    ids = previous_anchor_log_ids(scope_rows, focal)
    assert ids == [a]
