"""Unit tests for tier-change pricing and guard logic."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.pricing_service import prorate_tier_change


# ── helpers ───────────────────────────────────────────────────────────────


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


# ── prorate_tier_change ───────────────────────────────────────────────────


class TestProrateFullPeriod:
    """Charged from day 1 — remaining == full period."""

    def test_basic_upgrade_full_period(self):
        result = prorate_tier_change(
            old_price_per_seat=1000,
            new_price_per_seat=2000,
            covered_users=5,
            period_months=1,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 1, 30),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 1),
        )
        # diff_per_seat = 1000; period_seat_price = 1000*1 = 1000
        # period_days = 30, remaining = 30, daily = round_up(1000/30) = 33.34
        # prorated = 33.34 * 30 * 5 = 5001.00
        assert result["tier_diff_per_seat"] == Decimal("1000")
        assert result["covered_users"] == 5
        assert result["currency_code"] == "NGN"
        assert result["prorated_charge"] == Decimal("5001.00")

    def test_multi_month_period(self):
        result = prorate_tier_change(
            old_price_per_seat=1000,
            new_price_per_seat=2000,
            covered_users=1,
            period_months=3,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 3, 31),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 1),
        )
        # diff=1000; period_seat_price = 1000*3 = 3000
        # period_days = (Mar31 - Jan1).days+1 = 90
        # daily = round_up(3000/90)=33.34; prorated = 33.34*90*1 = 3000.60
        assert result["period_months"] == 3
        assert result["tier_diff_per_seat"] == Decimal("1000")

    def test_returns_expected_keys(self):
        result = prorate_tier_change(
            old_price_per_seat=500,
            new_price_per_seat=1500,
            covered_users=2,
            period_months=1,
            period_start=_dt(2026, 6, 1),
            period_end=_dt(2026, 6, 30),
            currency_code="NGN",
            country_code="NG",
        )
        for key in (
            "old_price_per_seat",
            "new_price_per_seat",
            "tier_diff_per_seat",
            "covered_users",
            "period_months",
            "prorated_charge",
            "daily_seat_rate",
            "remaining_days",
            "period_days",
            "subtotal",
            "currency_code",
            "country_code",
        ):
            assert key in result, f"missing key: {key}"


class TestProrateHalfPeriod:
    """Upgrade happens mid-period — charged only for remaining days."""

    def test_half_period_remaining(self):
        result = prorate_tier_change(
            old_price_per_seat=1000,
            new_price_per_seat=2000,
            covered_users=2,
            period_months=1,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 1, 30),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 16),  # 15 days remaining
        )
        assert result["remaining_days"] == 15
        assert result["period_days"] == 30
        # daily = round_up(1000/30) = 33.34; charge = 33.34 * 15 * 2 = 1000.20
        assert result["prorated_charge"] == Decimal("1000.20")

    def test_one_day_remaining(self):
        result = prorate_tier_change(
            old_price_per_seat=1000,
            new_price_per_seat=2000,
            covered_users=3,
            period_months=1,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 1, 30),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 30),  # last day
        )
        assert result["remaining_days"] == 1
        # daily = round_up(1000/30) = 33.34; charge = 33.34 * 1 * 3 = 100.02
        assert result["prorated_charge"] == Decimal("100.02")


class TestProrateGuards:
    """Validation: downgrade attempt, equal price, covered_users."""

    def test_rejects_downgrade(self):
        with pytest.raises(ValueError, match="must exceed"):
            prorate_tier_change(
                old_price_per_seat=2000,
                new_price_per_seat=1000,  # lower
                covered_users=1,
                period_months=1,
                period_start=_dt(2026, 1, 1),
                period_end=_dt(2026, 1, 30),
                currency_code="NGN",
                country_code="NG",
            )

    def test_rejects_same_price(self):
        with pytest.raises(ValueError, match="must exceed"):
            prorate_tier_change(
                old_price_per_seat=1500,
                new_price_per_seat=1500,  # equal
                covered_users=1,
                period_months=1,
                period_start=_dt(2026, 1, 1),
                period_end=_dt(2026, 1, 30),
                currency_code="NGN",
                country_code="NG",
            )

    def test_covered_users_scales_charge(self):
        base = prorate_tier_change(
            old_price_per_seat=1000,
            new_price_per_seat=2000,
            covered_users=1,
            period_months=1,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 1, 30),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 1),
        )
        scaled = prorate_tier_change(
            old_price_per_seat=1000,
            new_price_per_seat=2000,
            covered_users=10,
            period_months=1,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 1, 30),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 1),
        )
        assert scaled["prorated_charge"] == base["prorated_charge"] * 10

    def test_small_diff_rounds_up(self):
        # diff = 0.01; period_seat_price = 0.01; daily = round_up(0.01/30)
        result = prorate_tier_change(
            old_price_per_seat="999.99",
            new_price_per_seat="1000.00",
            covered_users=1,
            period_months=1,
            period_start=_dt(2026, 1, 1),
            period_end=_dt(2026, 1, 30),
            currency_code="NGN",
            country_code="NG",
            as_of=_dt(2026, 1, 1),
        )
        assert result["tier_diff_per_seat"] == Decimal("0.01")
        # daily = round_up(0.01/30) = 0.01 (rounds up)
        assert result["daily_seat_rate"] == Decimal("0.01")
        # charge = 0.01 * 30 * 1 = 0.30
        assert result["prorated_charge"] == Decimal("0.30")
