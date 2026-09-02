"""Unit tests for marketplace purchase/entitlement helpers."""

from datetime import datetime, timedelta, timezone

from app.libs.ai_grant_entitlement import grant_is_entitled, is_purchased

_FID = "feature-1"
_FID_OTHER = "feature-2"


def _iso(delta_days: int) -> str:
    when = datetime.now(tz=timezone.utc) + timedelta(days=delta_days)
    return when.isoformat()


def test_is_purchased_false_when_no_grant():
    assert is_purchased([_FID], {}) is False


def test_is_purchased_true_for_active_unexpired_grant():
    grants = {_FID: {"status": "active", "expires_at": _iso(10)}}
    assert is_purchased([_FID], grants) is True


def test_is_purchased_false_when_grant_status_expired():
    grants = {_FID: {"status": "expired", "expires_at": _iso(-1)}}
    assert is_purchased([_FID], grants) is False


def test_is_purchased_true_for_active_grant_inside_renewal_grace():
    grants = {_FID: {"status": "active", "expires_at": _iso(-3)}}
    assert is_purchased([_FID], grants) is True


def test_is_purchased_false_for_active_grant_after_renewal_grace():
    grants = {_FID: {"status": "active", "expires_at": _iso(-8)}}
    assert is_purchased([_FID], grants) is False


def test_is_purchased_true_for_cancelled_grant_before_expires_at():
    grants = {_FID: {"status": "cancelled", "expires_at": _iso(2)}}
    assert is_purchased([_FID], grants) is True


def test_is_purchased_false_for_cancelled_grant_after_expires_at():
    grants = {_FID: {"status": "cancelled", "expires_at": _iso(-1)}}
    assert is_purchased([_FID], grants) is False


def test_is_purchased_true_for_free_grant_regardless_of_status():
    grants = {_FID: {"status": "expired", "is_free": True}}
    assert is_purchased([_FID], grants) is True


def test_is_purchased_true_if_any_child_feature_is_entitled():
    grants = {
        _FID: {"status": "expired", "expires_at": _iso(-1)},
        _FID_OTHER: {"status": "active", "expires_at": _iso(10)},
    }
    assert is_purchased([_FID, _FID_OTHER], grants) is True


def test_grant_is_entitled_false_for_missing_grant():
    assert grant_is_entitled(None) is False
