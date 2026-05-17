import pytest

from app.domain.log_feature_store import historical_vectors_for_scope
from app.domain.scopes import AnalysisScope
from app.pipeline.anomaly_pipeline import (
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
    assert feats["hour_of_day"] == 23.0
    assert feats["visitor_total_visits"] == 2.0
    assert feats["relationship_transition"] == 0.0
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
    assert feats["hour_of_day"] == 22.0
    assert feats["resident_visit_frequency"] > 0
    assert "visitor_total_visits" not in feats


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
        "guard_total_validations",
        "guard_night_validations",
        "night_visit_flag",
        "hour_of_day",
    }


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
