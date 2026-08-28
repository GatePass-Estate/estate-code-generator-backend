import pytest

from app.libs.entitlement_validation import (
    ensure_admin_fee_entitlement,
    validate_entitlements,
)
from app.services.pricing_service import ADMIN_FEE_KEY

CATALOG = {
    "broadcasts_announcements": "boolean",
    "visit_access_history": "duration_days",
    "max_active_users": "count",
    "administrative_fee": "boolean",
}


def test_valid_entitlements():
    assert (
        validate_entitlements(
            {
                "broadcasts_announcements": True,
                "visit_access_history": 30,
                "max_active_users": 10,
            },
            CATALOG,
        )["visit_access_history"]
        == 30
    )


def test_unknown_key():
    with pytest.raises(ValueError, match="Unknown entitlement key"):
        validate_entitlements({"nope": True}, CATALOG)


def test_wrong_boolean_type():
    with pytest.raises(ValueError, match="boolean"):
        validate_entitlements({"broadcasts_announcements": 1}, CATALOG)


def test_negative_count():
    with pytest.raises(ValueError, match=">= 0"):
        validate_entitlements({"max_active_users": -1}, CATALOG)


def test_bool_rejected_for_count():
    with pytest.raises(ValueError):
        validate_entitlements({"max_active_users": True}, CATALOG)


def test_ensure_admin_fee_defaults_true_when_missing():
    result = ensure_admin_fee_entitlement({"broadcasts_announcements": True})
    assert result[ADMIN_FEE_KEY] is True
    assert result["broadcasts_announcements"] is True


def test_ensure_admin_fee_preserves_explicit_false():
    result = ensure_admin_fee_entitlement({ADMIN_FEE_KEY: False})
    assert result[ADMIN_FEE_KEY] is False
