import pytest

from app.core.feature_config import active_feature_set_for_scope
from app.domain.log_feature_store import (
    historical_vectors_for_scope,
    historical_vectors_for_scope_matching_active,
)
from app.domain.scopes import AnalysisScope
from app.pipeline.spatial_anomaly_pipeline import (
    ResidentAnomalyPipeline,
    VisitorAnomalyPipeline,
)


def _visitor_ctx_focal_second():
    return {
        "security_id": "sec-1",
        "valid_until": "2026-04-13T12:00:00+00:00",
        "history_window_days": 30.0,
        "focal_record": {
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "hashed_code": "abc123hash",
            "visitor_fullname": "Ada Visitor",
            "relationship_with_resident": "friend",
            "visit_time": "2026-04-12T23:00:00+00:00",
        },
    }


@pytest.mark.asyncio
async def test_visitor_scope_focal_not_mean_of_all_rows():
    pipeline = VisitorAnomalyPipeline()
    records = [
        {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "visitor_fullname": "Ada Visitor",
            "relationship_with_resident": "friend",
            "visit_time": "2026-04-10T10:00:00+00:00",
            "hashed_code": "abc123hash",
            "security_id": "sec-1",
        },
        {
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "visitor_fullname": "Ada Visitor",
            "relationship_with_resident": "friend",
            "visit_time": "2026-04-12T23:00:00+00:00",
            "hashed_code": "abc123hash",
            "security_id": "sec-1",
        },
    ]
    ctx = _visitor_ctx_focal_second()
    feats = await pipeline.engineer_scope_features(
        AnalysisScope.VISITOR,
        records,
        ctx,
    )
    assert feats["visitor_time_since_last_visit"] == pytest.approx(61.0)
    assert "hour_of_day" not in feats
    assert feats["relationship_transition"] == 0.0
    assert "visitor_total_visits" not in feats
    assert "guard_total_validations" not in feats


@pytest.mark.asyncio
async def test_resident_scope_uses_focal_hour():
    pipeline = ResidentAnomalyPipeline()
    records = [
        {
            "id": "a",
            "user_id": "resident-1",
            "access_time": "2026-04-01T08:00:00+00:00",
            "security_id": "sec-1",
        },
        {
            "id": "b",
            "user_id": "resident-1",
            "access_time": "2026-04-03T22:00:00+00:00",
            "security_id": "sec-1",
        },
    ]
    ctx = {
        "security_id": "sec-1",
        "user_id": "resident-1",
        "valid_until": "2026-04-04T00:00:00+00:00",
        "history_window_days": 30.0,
        "focal_record": {
            "id": "b",
            "user_id": "resident-1",
            "access_time": "2026-04-03T22:00:00+00:00",
        },
    }
    feats = await pipeline.engineer_scope_features(
        AnalysisScope.RESIDENT,
        records,
        ctx,
    )
    assert feats["resident_time_since_last_visit"] == pytest.approx(62.0)
    assert "hour_of_day" not in feats
    assert feats["resident_visit_frequency"] > 0
    assert "visitor_total_visits" not in feats
    assert "time_since_last_visit" not in feats


@pytest.mark.asyncio
async def test_engineer_only_invokes_keys_for_scope():
    pipeline = VisitorAnomalyPipeline()
    records = [{"id": "1", "visit_time": "2026-01-01T12:00:00Z"}]
    ctx = {
        "focal_record": records[0],
        "history_window_days": 30.0,
    }
    feats = await pipeline.engineer_scope_features(
        AnalysisScope.SECURITY,
        records,
        ctx,
    )
    assert set(feats.keys()) == {
        "guard_night_validation_frequency",
        "guard_night_validation_share",
    }
    assert feats["guard_night_validation_share"] == 0.0


@pytest.mark.asyncio
async def test_guard_night_validation_share_counts_night_rows():
    pipeline = VisitorAnomalyPipeline()
    records = [
        {
            "id": "1",
            "visit_time": "2026-01-01T12:00:00Z",
            "security_id": "sec-1",
        },
        {
            "id": "2",
            "visit_time": "2026-01-02T23:00:00Z",
            "security_id": "sec-1",
        },
    ]
    ctx = {
        "security_id": "sec-1",
        "focal_record": records[1],
        "history_window_days": 30.0,
    }
    feats = await pipeline.engineer_scope_features(
        AnalysisScope.SECURITY,
        records,
        ctx,
    )
    assert feats["guard_night_validation_share"] == pytest.approx(0.5)
    assert feats["guard_night_validation_frequency"] == pytest.approx(
        1.0 / (30.0 / 7.0)
    )


@pytest.mark.asyncio
async def test_temporal_scope_only_focal_clock_features():
    pipeline = VisitorAnomalyPipeline()
    records = [
        {
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "visitor_fullname": "Ada Visitor",
            "visit_time": "2026-04-12T23:00:00+00:00",
            "security_id": "sec-1",
        },
    ]
    ctx = {
        "security_id": "sec-1",
        "focal_record": records[0],
        "history_window_days": 30.0,
    }
    feats = await pipeline.engineer_scope_features(
        AnalysisScope.TEMPORAL,
        records,
        ctx,
    )
    assert set(feats.keys()) == {
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "visit_hour_bucket",
        "night_visit_flag",
    }
    assert feats["hour_of_day"] == 23.0
    assert feats["night_visit_flag"] == 1.0


def test_historical_vectors_skip_anomalous_rows():
    stored = [
        {
            "is_anomalous": False,
            "features_security_specific": {"a": 1.0},
        },
        {
            "is_anomalous": True,
            "features_security_specific": {"a": 99.0},
        },
        {"features_security_specific": {"a": 2.0}},
    ]
    vecs = historical_vectors_for_scope(stored, AnalysisScope.SECURITY)
    assert vecs == [{"a": 1.0}, {"a": 2.0}]


def test_historical_vectors_matching_active_excludes_legacy_schema():
    active = active_feature_set_for_scope(AnalysisScope.SECURITY)
    legacy = {k: float(i) for i, k in enumerate(sorted(active))}
    stored = [
        {
            "is_anomalous": False,
            "features_security_specific": legacy,
        },
        {
            "is_anomalous": False,
            "features_security_specific": {
                "guard_total_validations": 10.0,
                "hour_of_day": 8.0,
            },
        },
    ]
    matched, excluded = historical_vectors_for_scope_matching_active(
        stored, AnalysisScope.SECURITY
    )
    assert len(matched) == 1
    assert excluded == 1
    assert set(matched[0].keys()) == active
