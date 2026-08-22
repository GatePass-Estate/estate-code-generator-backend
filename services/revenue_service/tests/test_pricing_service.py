"""Unit tests for pricing math (no DB)."""

from decimal import Decimal

import pytest

from app.services.pricing_service import (
    compute_ai_monthly,
    compute_client_total,
    compute_price_per_seat,
    quote_pricing,
)


def test_price_per_seat_excludes_then_adds_admin_fee():
    prices = {
        "guest_contact_management": 200,
        "broadcasts_announcements": 250,
        "basic_reporting_exports": 200,
        "estate_account_lifecycle": 150,
        "administrative_fee": 700,
        "personal_resident_access_code": 0,
    }
    result = compute_price_per_seat(
        prices,
        [
            "guest_contact_management",
            "broadcasts_announcements",
            "basic_reporting_exports",
            "estate_account_lifecycle",
            "administrative_fee",
            "personal_resident_access_code",
        ],
    )
    assert result["sum_of_included_features"] == Decimal("800")
    assert result["administrative_fee"] == Decimal("700")
    assert result["price_per_seat"] == Decimal("1500")


def test_ai_monthly_not_seat_scaled():
    ai = compute_ai_monthly(
        {
            "visitor_resident_anomaly_detection": 500,
            "incident_summary_basic": 500,
        },
        ["visitor_resident_anomaly_detection", "incident_summary_basic"],
    )
    assert ai["ai_price_per_month"] == Decimal("1000")


def test_client_total_formula():
    totals = compute_client_total(
        price_per_seat=1500,
        seats=10,
        ai_price_per_month=1000,
        period_months=3,
    )
    # (1500*10 + 1000) * 3 = 48000
    assert totals["client_total"] == Decimal("48000")
    assert totals["monthly_subtotal"] == Decimal("16000")


def test_command_rollup_one_seat_one_month():
    service_prices = {
        "guest_contact_management": 200,
        "broadcasts_announcements": 250,
        "basic_reporting_exports": 200,
        "estate_account_lifecycle": 150,
        "priority_support": 500,
        "administrative_fee": 700,
    }
    ai_prices = {
        "visitor_resident_anomaly_detection": 500,
        "incident_summary_basic": 500,
        "pattern_analysis": 200,
        "spatial_temporal_anomaly_detection": 300,
        "incident_theme_analysis": 200,
        "volume_forecasting": 200,
        "ai_generated_incident_narrative": 100,
    }
    quote = quote_pricing(
        service_prices=service_prices,
        ai_prices=ai_prices,
        included_service_keys=list(service_prices.keys()),
        ai_feature_keys=list(ai_prices.keys()),
        seats=1,
        period_months=1,
        currency_code="NGN",
        country_code="NG",
    )
    assert quote["price_per_seat"] == Decimal("2000")
    assert quote["ai_price_per_month"] == Decimal("2000")
    assert quote["client_total"] == Decimal("4000")


def test_missing_price_raises():
    with pytest.raises(ValueError, match="Missing feature_unit_price"):
        compute_price_per_seat({"a": 1}, ["a", "b"])


def test_invalid_period():
    with pytest.raises(ValueError):
        compute_client_total(
            price_per_seat=1, seats=1, ai_price_per_month=0, period_months=0
        )
