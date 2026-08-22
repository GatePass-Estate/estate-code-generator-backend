"""Unit tests for entitlement resolver precedence."""

from app.services.entitlement_resolver import (
    check_service_entitlement,
    resolve_entitlements,
)

ACCESS = {
    "slug": "access",
    "is_custom": False,
    "entitlements": {
        "personal_resident_access_code": True,
        "broadcasts_announcements": False,
        "visit_access_history": 7,
    },
}

WATCH = {
    "slug": "watch",
    "is_custom": False,
    "entitlements": {
        "personal_resident_access_code": True,
        "broadcasts_announcements": True,
        "visit_access_history": 365,
    },
}

ENTERPRISE = {
    "slug": "enterprise",
    "is_custom": True,
    "entitlements": {},
}


def test_no_subscription_uses_access():
    result = resolve_entitlements(
        subscription=None, tier=None, access_tier=ACCESS
    )
    assert result == ACCESS["entitlements"]


def test_expired_falls_back_to_access():
    sub = {"status": "expired", "entitlements": None}
    result = resolve_entitlements(
        subscription=sub, tier=WATCH, access_tier=ACCESS
    )
    assert result["broadcasts_announcements"] is False
    assert result["visit_access_history"] == 7


def test_past_due_falls_back_to_access():
    sub = {"status": "past_due", "entitlements": None}
    result = resolve_entitlements(
        subscription=sub, tier=WATCH, access_tier=ACCESS
    )
    assert result == ACCESS["entitlements"]


def test_active_uses_tier_entitlements():
    sub = {"status": "active", "entitlements": None}
    result = resolve_entitlements(
        subscription=sub, tier=WATCH, access_tier=ACCESS
    )
    assert result["broadcasts_announcements"] is True
    assert result["visit_access_history"] == 365


def test_trialing_uses_tier_entitlements():
    sub = {"status": "trialing", "entitlements": None}
    result = resolve_entitlements(
        subscription=sub, tier=WATCH, access_tier=ACCESS
    )
    assert result["broadcasts_announcements"] is True


def test_custom_uses_subscription_snapshot():
    snapshot = {
        "personal_resident_access_code": True,
        "broadcasts_announcements": True,
        "priority_support": True,
        "visit_access_history": 90,
    }
    sub = {"status": "active", "entitlements": snapshot}
    result = resolve_entitlements(
        subscription=sub, tier=ENTERPRISE, access_tier=ACCESS
    )
    assert result == snapshot


def test_custom_with_empty_snapshot():
    sub = {"status": "active", "entitlements": {}}
    result = resolve_entitlements(
        subscription=sub, tier=ENTERPRISE, access_tier=ACCESS
    )
    assert result == {}


def test_check_boolean_and_count():
    ents = {"broadcasts_announcements": True, "visit_access_history": 30}
    assert (
        check_service_entitlement(ents, "broadcasts_announcements", "boolean")[
            "allowed"
        ]
        is True
    )
    assert check_service_entitlement(
        ents, "visit_access_history", "duration_days"
    ) == {
        "allowed": True,
        "limit": 30,
        "limit_type": "duration_days",
    }
    assert (
        check_service_entitlement(ents, "priority_support", "boolean")[
            "allowed"
        ]
        is False
    )
