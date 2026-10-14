"""Unit tests for subscription tier feature availability."""

from app.services.revenue.tier_feature_availability import (
    build_tier_feature_availability,
    tier_includes_ai_feature,
    tier_includes_paid_service,
)


def test_watch_tier_paid_features_split():
    tier = {
        "slug": "watch",
        "is_custom": False,
        "entitlements": {
            "guest_management": True,
            "extended_historical_record": 90,
        },
        "included_ai_features": [],
    }
    free, paid, ai = build_tier_feature_availability(
        tier,
        service_catalog_rows=[
            {
                "service_key": "guest_management",
                "name": "Guest Management",
                "limit_type": "boolean",
            },
            {
                "service_key": "incident_report",
                "name": "Incident Reporting",
                "limit_type": "boolean",
            },
        ],
        ai_feature_rows=[
            {
                "feature_key": "access_anomaly_detection_tier_1",
                "name": "Anomaly Scan",
            },
        ],
    )
    assert len(free.available) == 5
    assert free.unavailable == []
    assert [f.service_key for f in paid.available] == [
        "guest_management",
    ]
    assert [f.service_key for f in paid.unavailable] == ["incident_report"]
    assert paid.available[0].label == "Guest Management"
    assert ai.available == []
    assert [f.feature_key for f in ai.unavailable] == [
        "access_anomaly_detection_tier_1"
    ]


def test_custom_tier_all_paid_and_ai_available():
    tier = {
        "slug": "custom",
        "is_custom": True,
        "entitlements": {},
        "included_ai_features": [],
    }
    _, paid, ai = build_tier_feature_availability(
        tier,
        service_catalog_rows=[
            {
                "service_key": "incident_report",
                "name": "Incident Reporting",
                "limit_type": "boolean",
            },
        ],
        ai_feature_rows=[
            {
                "feature_key": "incident_report_summary_tier_1",
                "name": "Incident Insights",
            },
        ],
    )
    assert len(paid.available) == 1
    assert paid.unavailable == []
    assert len(ai.available) == 1
    assert ai.unavailable == []


def test_duration_days_entitlement():
    tier = {
        "slug": "watch",
        "is_custom": False,
        "entitlements": {"extended_historical_record": 90},
        "included_ai_features": [],
    }
    assert tier_includes_paid_service(
        tier,
        service_key="extended_historical_record",
        limit_type="duration_days",
    )
    assert not tier_includes_paid_service(
        {
            "slug": "access",
            "is_custom": False,
            "entitlements": {},
            "included_ai_features": [],
        },
        service_key="extended_historical_record",
        limit_type="duration_days",
    )


def test_ai_included_list():
    tier = {
        "slug": "sentinel",
        "is_custom": False,
        "entitlements": {},
        "included_ai_features": ["access_anomaly_detection_tier_1"],
    }
    assert tier_includes_ai_feature(tier, "access_anomaly_detection_tier_1")
    assert not tier_includes_ai_feature(
        tier, "access_anomaly_detection_tier_3"
    )
