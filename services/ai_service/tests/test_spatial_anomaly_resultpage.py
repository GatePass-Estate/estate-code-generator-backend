"""Normal-behaviour averaging for the spatial-anomaly result page."""

from copy import deepcopy

import pytest

from app.models.spatial_anomaly_resultpage import Severity
from app.pipeline.spatial_anomaly_resultpage import (
    SPIDER_TOP_N,
    build_anomaly_overview,
    case_results_from_db_payload,
    overview_from_db_payload,
)


def _scope(name: str, score: float, features: list[dict]) -> dict:
    return {
        "scope": name,
        "score": score,
        "feature_contributions": features,
    }


def _fc(name: str, value: float, weight: float | None) -> dict:
    return {
        "feature_name": name,
        "value": value,
        "weight": weight,
        "contribution": None,
    }


def test_build_anomaly_overview_averages_and_picks_top_six():
    sample = [
        {
            "result": {
                "is_anomalous": False,
                "transparency": {
                    "scopes": [
                        _scope(
                            "visitor_specific",
                            0.2,
                            [
                                _fc("hour_of_day", 8.0, 0.9),
                                _fc("day_of_week", 3.0, 0.4),
                                _fc("is_weekend", 0.0, 0.1),
                            ],
                        ),
                        _scope(
                            "estate_wide",
                            0.4,
                            [
                                _fc("hour_of_day", 10.0, 0.7),
                                _fc("night_visit_flag", 0.0, 0.8),
                                _fc("guard_total_validations", 20.0, 0.6),
                                _fc("visitor_weekly_frequency", 2.0, 0.5),
                                _fc("resident_visit_frequency", 3.0, 0.3),
                            ],
                        ),
                    ]
                },
            }
        },
        {
            "result": {
                "is_anomalous": False,
                "transparency": {
                    "scopes": [
                        _scope(
                            "visitor_specific",
                            0.4,
                            [
                                _fc("hour_of_day", 12.0, 0.9),
                                _fc("day_of_week", 5.0, 0.4),
                            ],
                        )
                    ]
                },
            }
        },
    ]

    overview = build_anomaly_overview(
        sample,
        feature_max_values={"hour_of_day": 22.0},
        scope_max_scores={"visitor_specific": 0.9},
        scope_feature_max_values={
            "visitor_specific": {"hour_of_day": 22.0},
        },
    )
    assert len(overview.spider_plot) == SPIDER_TOP_N
    assert overview.spider_plot == overview.top_contributing_factors
    names = [p.feature_name for p in overview.spider_plot]
    assert names[0] == "hour_of_day"
    hour = overview.spider_plot[0]
    assert hour.normal_value == 10.0
    assert hour.weight == pytest.approx(0.833333)
    assert hour.scale == pytest.approx(22.0)
    assert hour.percentage == pytest.approx(45.45)

    by_scope = {f.name: f for f in overview.contributing_factors}
    assert [f.name for f in overview.contributing_factors] == [
        "visitor_specific",
        "resident_specific",
        "security_specific",
        "estate_wide",
    ]
    visitor_hour = next(
        s
        for s in by_scope["visitor_specific"].sub_factors
        if s.feature_name == "hour_of_day"
    )
    assert visitor_hour.normal_value == 10.0
    assert visitor_hour.scale == pytest.approx(22.0)
    assert visitor_hour.percentage == pytest.approx(45.45)
    assert by_scope["visitor_specific"].normal_value == 0.3
    assert by_scope["visitor_specific"].scale == pytest.approx(0.9)
    assert by_scope["visitor_specific"].percentage == pytest.approx(33.33)


def test_overview_factors_use_period_max_keys_when_sample_misses_scope():
    sample = [
        {
            "result": {
                "is_anomalous": False,
                "transparency": {
                    "scopes": [
                        _scope(
                            "estate_wide",
                            0.4,
                            [_fc("hour_of_day", 10.0, 0.7)],
                        )
                    ]
                },
            }
        }
    ]
    overview = build_anomaly_overview(
        sample,
        feature_max_values={"hour_of_day": 22.0},
        scope_max_scores={"visitor_specific": 0.98, "estate_wide": 0.9},
        scope_feature_max_values={
            "visitor_specific": {
                "hour_of_day": 22.0,
                "visitor_weekly_frequency": 4.9,
            },
            "estate_wide": {"hour_of_day": 22.0},
        },
    )
    by_scope = {f.name: f for f in overview.contributing_factors}
    visitor = by_scope["visitor_specific"]
    names = [s.feature_name for s in visitor.sub_factors]
    assert "hour_of_day" in names
    assert "visitor_weekly_frequency" in names
    hour = next(
        s for s in visitor.sub_factors if s.feature_name == "hour_of_day"
    )
    assert hour.normal_value is None
    assert hour.scale == pytest.approx(22.0)


def test_build_anomaly_overview_handles_null_weights_and_empty_sample():
    empty = build_anomaly_overview([])
    assert empty.spider_plot == []
    assert [f.name for f in empty.contributing_factors] == [
        "visitor_specific",
        "resident_specific",
        "security_specific",
        "estate_wide",
    ]
    assert all(f.sub_factors == [] for f in empty.contributing_factors)

    raw = {
        "transparency": {
            "scopes": [
                _scope(
                    "security_specific",
                    0.0,
                    [_fc("hour_of_day", 8.0, None)],
                )
            ]
        }
    }
    overview = build_anomaly_overview([raw])
    assert overview.spider_plot[0].feature_name == "hour_of_day"
    assert overview.spider_plot[0].weight is None
    by_scope = {f.name: f for f in overview.contributing_factors}
    assert by_scope["security_specific"].sub_factors[0].weight is None
    assert [f.name for f in overview.contributing_factors] == [
        "visitor_specific",
        "resident_specific",
        "security_specific",
        "estate_wide",
    ]


def test_overview_from_db_payload_maps_demographic_fields():
    payload = {
        "estate_name": "Lekki Gardens",
        "state": "Lagos",
        "country": "Nigeria",
        "total_guests": 12,
        "resident_count": 30,
        "security_count": 5,
        "total_anomalous_instances": 9,
        "total_high_risk_instances": 4,
        "total_anomalous_residents_instances": 2,
        "total_anomalous_visitors_instances": 7,
        "normal_sample": [],
        "feature_max_values": {},
        "scope_max_scores": {},
        "scope_feature_max_values": {},
    }
    result = overview_from_db_payload(deepcopy(payload))
    assert result.demographic.estate_name == "Lekki Gardens"
    assert result.demographic.total_users == 42
    assert result.demographic.ratio["guest"].count == 12
    assert result.demographic.ratio["guest"].percentage == 25.53
    assert result.demographic.ratio["resident"].count == 30
    assert result.demographic.ratio["resident"].percentage == 63.83
    assert result.demographic.ratio["security"].count == 5
    assert result.demographic.ratio["security"].percentage == 10.64
    assert result.demographic.total_anomalous_instances == 9
    assert result.demographic.total_high_risk_instances == 4
    assert result.evidence_summary.total_anomalous_visitors_instances == 7
    assert result.anomaly_overview.spider_plot == []
    assert [f.name for f in result.anomaly_overview.contributing_factors] == [
        "visitor_specific",
        "resident_specific",
        "security_specific",
        "estate_wide",
    ]


def test_build_case_anomaly_overview_overlays_instance_on_normal():
    from app.pipeline.spatial_anomaly_resultpage import (
        build_case_anomaly_overview,
    )

    sample = [
        {
            "result": {
                "is_anomalous": False,
                "transparency": {
                    "scopes": [
                        _scope(
                            "visitor_specific",
                            0.2,
                            [_fc("hour_of_day", 8.0, 0.9)],
                        )
                    ]
                },
            }
        }
    ]
    instance = {
        "result": {
            "is_anomalous": True,
            "final_score": 0.9,
            "transparency": {
                "scopes": [
                    _scope(
                        "visitor_specific",
                        0.7,
                        [_fc("hour_of_day", 22.0, 0.9)],
                    )
                ]
            },
        }
    }
    overview = build_case_anomaly_overview(
        instance,
        sample,
        feature_max_values={"hour_of_day": 22.0},
        scope_max_scores={"visitor_specific": 0.7},
        scope_feature_max_values={
            "visitor_specific": {"hour_of_day": 22.0},
        },
    )
    hour = overview.spider_plot[0]
    assert hour.feature_name == "hour_of_day"
    assert hour.normal_value == pytest.approx(8.0)
    assert hour.instance_value == pytest.approx(22.0)
    assert hour.scale == pytest.approx(22.0)
    assert hour.percentage == pytest.approx(36.36)
    assert hour.instance_percentage == pytest.approx(100.0)
    visitor = overview.contributing_factors[0]
    assert visitor.name == "visitor_specific"
    assert visitor.instance_value == pytest.approx(0.7)
    assert visitor.scale == pytest.approx(0.7)
    assert visitor.percentage == pytest.approx(100.0)
    assert visitor.sub_factors[0].instance_value == pytest.approx(22.0)


def test_case_contributing_factors_follow_prediction_scopes():
    from app.pipeline.spatial_anomaly_resultpage import (
        build_case_anomaly_overview,
    )

    sample = [
        {
            "result": {
                "is_anomalous": False,
                "transparency": {
                    "scopes": [
                        _scope(
                            "visitor_specific",
                            0.2,
                            [_fc("hour_of_day", 8.0, 0.9)],
                        ),
                        _scope(
                            "resident_specific",
                            0.3,
                            [_fc("hour_of_day", 9.0, 0.8)],
                        ),
                        _scope(
                            "estate_wide",
                            0.4,
                            [_fc("hour_of_day", 10.0, 0.7)],
                        ),
                    ]
                },
            }
        }
    ]
    instance = {
        "result": {
            "anomaly_type": "resident",
            "is_anomalous": True,
            "final_score": 0.9,
            "transparency": {
                "scopes": [
                    _scope(
                        "visitor_specific",
                        0.1,
                        [_fc("hour_of_day", 22.0, 0.9)],
                    ),
                    _scope(
                        "resident_specific",
                        0.7,
                        [_fc("hour_of_day", 22.0, 0.9)],
                    ),
                    _scope(
                        "estate_wide",
                        0.8,
                        [_fc("hour_of_day", 22.0, 0.9)],
                    ),
                ]
            },
        }
    }
    overview = build_case_anomaly_overview(
        instance,
        sample,
        feature_max_values={"hour_of_day": 22.0},
        scope_max_scores={
            "visitor_specific": 0.7,
            "resident_specific": 0.7,
            "estate_wide": 0.8,
        },
        scope_feature_max_values={
            "visitor_specific": {"hour_of_day": 22.0},
            "resident_specific": {"hour_of_day": 22.0},
            "estate_wide": {"hour_of_day": 22.0},
        },
    )
    names = [f.name for f in overview.contributing_factors]
    assert names == [
        "resident_specific",
        "security_specific",
        "estate_wide",
    ]
    assert "visitor_specific" not in names

    instance["result"]["anomaly_type"] = "visitor"
    visitor_overview = build_case_anomaly_overview(
        instance,
        sample,
        feature_max_values={"hour_of_day": 22.0},
        scope_max_scores={
            "visitor_specific": 0.7,
            "resident_specific": 0.7,
            "estate_wide": 0.8,
        },
        scope_feature_max_values={
            "visitor_specific": {"hour_of_day": 22.0},
            "resident_specific": {"hour_of_day": 22.0},
            "estate_wide": {"hour_of_day": 22.0},
        },
    )
    assert [f.name for f in visitor_overview.contributing_factors] == [
        "visitor_specific",
        "resident_specific",
        "security_specific",
        "estate_wide",
    ]


def test_case_spider_plot_skips_features_missing_on_instance():
    from app.pipeline.spatial_anomaly_resultpage import (
        SPIDER_TOP_N,
        build_case_anomaly_overview,
    )

    ranked = [
        ("visitor_weekly_frequency", 0.9, 1.0),
        ("visitor_total_visits", 0.8, 2.0),
        ("visit_interarrival_time", 0.7, 0.1),
        ("visit_hour_bucket", 0.6, 2.0),
        ("time_since_last_visit", 0.5, 0.1),
        ("resident_visit_frequency", 0.4, 1.0),
        ("hour_of_day", 0.3, 8.0),
    ]
    sample = [
        {
            "result": {
                "is_anomalous": False,
                "transparency": {
                    "scopes": [
                        _scope(
                            "visitor_specific",
                            0.2,
                            [
                                _fc(name, value, weight)
                                for name, weight, value in ranked
                            ],
                        )
                    ]
                },
            }
        }
    ]
    instance_feats = [
        _fc(name, value + 1.0, weight)
        for name, weight, value in ranked
        if name != "visitor_total_visits"
    ]
    instance = {
        "result": {
            "is_anomalous": True,
            "final_score": 0.9,
            "transparency": {
                "scopes": [
                    _scope("visitor_specific", 0.7, instance_feats),
                ]
            },
        }
    }
    overview = build_case_anomaly_overview(
        instance,
        sample,
        feature_max_values={name: 20.0 for name, _, _ in ranked},
    )
    names = [p.feature_name for p in overview.spider_plot]
    assert len(names) == SPIDER_TOP_N
    assert "visitor_total_visits" not in names
    assert "hour_of_day" in names
    assert all(p.instance_value is not None for p in overview.spider_plot)


def test_case_results_from_db_payload_maps_score_and_severity():
    instance = {
        "result": {
            "is_anomalous": True,
            "final_score": 0.9,
            "transparency": {
                "scopes": [
                    _scope(
                        "visitor_specific",
                        0.7,
                        [_fc("hour_of_day", 22.0, 0.9)],
                    )
                ]
            },
        }
    }
    payload = {
        "prediction_id": "pred-1",
        "result": instance,
        "normal_sample": [],
        "feature_max_values": {"hour_of_day": 22.0},
        "scope_max_scores": {"visitor_specific": 0.7},
        "scope_feature_max_values": {
            "visitor_specific": {"hour_of_day": 22.0},
        },
    }
    result = case_results_from_db_payload(payload, prediction_id="fallback")
    assert result.prediction_id == "pred-1"
    assert result.final_score == pytest.approx(0.9)
    assert result.is_anomalous is True
    assert result.severity == Severity.HIGH
    assert result.anomaly_overview.spider_plot[0].instance_value == 22.0


def test_build_inhouse_summary_has_executive_and_detail():
    from app.pipeline.spatial_anomaly_case_summary import (
        build_inhouse_summary,
    )

    raw = {
        "result": {
            "is_anomalous": True,
            "final_score": 0.91,
            "anomaly_type": "visitor",
            "transparency": {
                "scopes": [
                    _scope(
                        "visitor_specific",
                        0.8,
                        [_fc("hour_of_day", 22.0, 0.9)],
                    )
                ]
            },
        }
    }
    report = build_inhouse_summary(raw)
    assert "anomalous" in report.executive_summary
    assert "0.910" in report.executive_summary
    assert "high" in report.executive_summary
    assert "hour of day" in report.detailed_insight.lower()
    assert "visitor" in report.detailed_insight.lower()


def test_require_estate_membership_allows_matching_estate():
    from uuid import UUID

    from app.api.v1.endpoints.spatial_anomaly_resultpage import (
        _require_estate_membership,
    )

    estate_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    _require_estate_membership({"estate_id": str(estate_id)}, estate_id)


def test_require_estate_membership_rejects_mismatch_and_missing():
    from uuid import UUID

    from fastapi import HTTPException

    from app.api.v1.endpoints.spatial_anomaly_resultpage import (
        _require_estate_membership,
    )

    estate_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    other = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    with pytest.raises(HTTPException) as mismatch:
        _require_estate_membership({"estate_id": str(other)}, estate_id)
    assert mismatch.value.status_code == 403

    with pytest.raises(HTTPException) as missing:
        _require_estate_membership({"estate_id": None}, estate_id)
    assert missing.value.status_code == 403


@pytest.mark.asyncio
async def test_get_case_summary_denies_when_estate_has_no_grant(monkeypatch):
    from uuid import UUID

    from app.core.exceptions import EntitlementDeniedError
    from app.services.spatial_anomaly_resultpage import (
        SpatialAnomalyResultPageService,
    )

    async def _denied(*_args, **_kwargs):
        return False

    monkeypatch.setattr(
        "app.services.spatial_anomaly_resultpage.is_ai_feature_allowed",
        _denied,
    )
    service = SpatialAnomalyResultPageService()
    with pytest.raises(EntitlementDeniedError) as denied:
        await service.get_case_summary(
            prediction_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            estate_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        )
    assert denied.value.status_code == 403
    assert "not entitled" in denied.value.message.lower()
