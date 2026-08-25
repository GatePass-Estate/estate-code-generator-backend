"""Unit tests for subscription period dating rules."""

from datetime import datetime, timedelta, timezone

from app.libs.period_dating import (
    compute_period_end,
    paid_feature_access_valid,
)


def test_first_subscribe_anchors_to_paid_at():
    paid = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = compute_period_end(
        paid_at=paid,
        duration=timedelta(days=30),
        old_period_end=None,
        grace_days=7,
    )
    assert end == paid + timedelta(days=30)


def test_manual_renew_inside_grace_extends_old_end():
    old_end = datetime(2026, 4, 1, tzinfo=timezone.utc)
    paid = old_end + timedelta(days=3)
    end = compute_period_end(
        paid_at=paid,
        duration=timedelta(days=30),
        old_period_end=old_end,
        grace_days=7,
    )
    assert end == old_end + timedelta(days=30)


def test_manual_renew_after_grace_anchors_to_paid_at():
    old_end = datetime(2026, 4, 1, tzinfo=timezone.utc)
    paid = old_end + timedelta(days=10)
    end = compute_period_end(
        paid_at=paid,
        duration=timedelta(days=30),
        old_period_end=old_end,
        grace_days=7,
    )
    assert end == paid + timedelta(days=30)


def test_active_paid_feature_keeps_access_during_grace():
    expires = datetime(2026, 4, 1, tzinfo=timezone.utc)
    now = expires + timedelta(days=3)
    assert paid_feature_access_valid(
        status="active",
        expires_at=expires.isoformat(),
        grace_days=7,
        now=now,
    )


def test_active_paid_feature_denied_after_grace():
    expires = datetime(2026, 4, 1, tzinfo=timezone.utc)
    now = expires + timedelta(days=8)
    assert not paid_feature_access_valid(
        status="active",
        expires_at=expires.isoformat(),
        grace_days=7,
        now=now,
    )


def test_cancelled_paid_feature_has_no_grace():
    expires = datetime(2026, 4, 1, tzinfo=timezone.utc)
    now = expires + timedelta(days=1)
    assert not paid_feature_access_valid(
        status="cancelled",
        expires_at=expires.isoformat(),
        grace_days=7,
        now=now,
    )


def test_past_due_paid_feature_has_no_grace():
    expires = datetime(2026, 4, 1, tzinfo=timezone.utc)
    now = expires + timedelta(hours=1)
    assert not paid_feature_access_valid(
        status="past_due",
        expires_at=expires.isoformat(),
        grace_days=7,
        now=now,
    )


def test_cancelled_paid_feature_allowed_before_expires_at():
    expires = datetime(2026, 4, 1, tzinfo=timezone.utc)
    now = expires - timedelta(hours=1)
    assert paid_feature_access_valid(
        status="cancelled",
        expires_at=expires.isoformat(),
        grace_days=7,
        now=now,
    )
