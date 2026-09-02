"""Unit tests for marketplace purchase/entitlement helpers."""

from datetime import datetime, timedelta, timezone

import pytest

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


def test_rating_request_rejects_oversized_comment():
    pytest.importorskip("pydantic")
    pytest.importorskip("pydantic_settings")
    from pydantic import ValidationError

    from app.core.config import settings
    from app.schemas.ai_market_place import RatingRequest, RatingSample

    limit = settings.RATING_COMMENT_MAX_LENGTH

    with pytest.raises(ValidationError):
        RatingRequest(score=5, comment="x" * (limit + 1))
    with pytest.raises(ValidationError):
        RatingSample(
            user_id="u1",
            score=5,
            comment="x" * (limit + 1),
        )

    ok = RatingRequest(score=5, comment="x" * limit)
    assert ok.comment is not None
    assert len(ok.comment) == limit

    sample = RatingSample(
        user_id="u1",
        score=5,
        comment="x" * limit,
    )
    assert sample.comment is not None
    assert len(sample.comment) == limit
