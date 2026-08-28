"""Unit tests for mid-period seat proration."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.pricing_service import compute_seat_proration


def test_seat_proration_half_period():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 30, tzinfo=timezone.utc)  # 30 days inclusive
    as_of = datetime(2026, 1, 16, tzinfo=timezone.utc)  # 15 remaining days
    result = compute_seat_proration(
        period_seat_price=3000,
        seats_added=2,
        period_start=start,
        period_end=end,
        as_of=as_of,
    )
    assert result["period_days"] == 30
    assert result["remaining_days"] == 15
    # daily = 3000/30 = 100; charge = 100 * 15 * 2 = 3000
    assert result["prorated_charge"] == Decimal("3000")


def test_seat_proration_rounds_charge_up_to_two_decimals():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 30, tzinfo=timezone.utc)
    as_of = datetime(2026, 1, 16, tzinfo=timezone.utc)
    result = compute_seat_proration(
        period_seat_price=1000,
        seats_added=1,
        period_start=start,
        period_end=end,
        as_of=as_of,
    )
    # daily = round_up(1000/30)=33.34; charge = 33.34 * 15 = 500.10
    assert result["daily_seat_rate"] == Decimal("33.34")
    assert result["prorated_charge"] == Decimal("500.10")

    result = compute_seat_proration(
        period_seat_price=1000,
        seats_added=1,
        period_start=start,
        period_end=end,
        as_of=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    # 29 remaining days: daily = round_up(1000/30)=33.34; charge = 33.34*29
    assert result["daily_seat_rate"] == Decimal("33.34")
    assert result["prorated_charge"] == Decimal("966.86")


def test_seat_proration_daily_rate_rounds_up():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 30, tzinfo=timezone.utc)
    result = compute_seat_proration(
        period_seat_price=1000,
        seats_added=1,
        period_start=start,
        period_end=end,
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert result["daily_seat_rate"] == Decimal("33.34")
    with pytest.raises(ValueError, match="seats_added"):
        compute_seat_proration(
            period_seat_price=100,
            seats_added=0,
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        )
