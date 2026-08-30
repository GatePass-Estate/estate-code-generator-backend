"""Normal-behaviour averaging for the spatial-anomaly result page."""

from copy import deepcopy

import pytest

from app.pipeline.spatial_anomaly_resultpage import (
    SPIDER_TOP_N,
    build_anomaly_overview,
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
    assert set(by_scope) == {"visitor_specific", "estate_wide"}
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


def test_build_anomaly_overview_handles_null_weights_and_empty_sample():
    empty = build_anomaly_overview([])
    assert empty.spider_plot == []
    assert empty.contributing_factors == []

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
    assert overview.contributing_factors[0].name == "security_specific"


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
