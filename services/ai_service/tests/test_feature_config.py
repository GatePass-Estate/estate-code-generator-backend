"""Active feature config and historical-vector schema matching."""

from app.core.feature_config import (
    active_feature_set_for_scope,
    active_features_for_scope,
    feature_label,
)
from app.domain import features as feat
from app.domain.log_feature_store import filter_vectors_by_active_keys
from app.domain.scopes import AnalysisScope


def test_active_features_exclude_retired_cumulative_keys():
    temporal_keys = set(active_features_for_scope(AnalysisScope.TEMPORAL))
    assert feat.HOUR_OF_DAY in temporal_keys
    assert feat.NIGHT_VISIT_FLAG in temporal_keys

    visitor_keys = set(active_features_for_scope(AnalysisScope.VISITOR))
    assert feat.VISITOR_TOTAL_VISITS not in visitor_keys
    assert feat.HOUR_OF_DAY not in visitor_keys
    assert feat.VISITOR_TIME_SINCE_LAST_VISIT in visitor_keys
    assert feat.RELATIONSHIP_FREQUENCY not in visitor_keys

    security_keys = set(active_features_for_scope(AnalysisScope.SECURITY))
    assert feat.GUARD_TOTAL_VALIDATIONS not in security_keys
    assert feat.HOUR_OF_DAY not in security_keys
    assert feat.GUARD_NIGHT_VALIDATION_FREQUENCY in security_keys


def test_feature_label_returns_human_readable_name():
    assert feature_label(feat.HOUR_OF_DAY) == "Hour of the Day"
    assert feature_label("unknown_feature_key") == "Unknown Feature Key"


def test_filter_vectors_by_active_keys_exact_match_only():
    active = active_feature_set_for_scope(AnalysisScope.SECURITY)
    vectors = [
        {k: 1.0 for k in active},
        {"hour_of_day": 12.0},
        {**{k: 1.0 for k in active}, "legacy_key": 9.0},
    ]
    matched, excluded = filter_vectors_by_active_keys(vectors, active)
    assert len(matched) == 1
    assert excluded == 2
