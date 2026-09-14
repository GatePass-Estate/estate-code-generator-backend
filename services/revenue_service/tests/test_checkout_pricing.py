"""Estate-type multiplier, VAT skip, and checkout VAT composition."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import checkout_service as checkout_mod
from app.services.checkout_service import CheckoutService
from app.services.pricing_service import apply_vat, omit_vat, quote_pricing


def test_omit_vat_drops_rate_key():
    assert omit_vat({"guest_management": True, "vat": True}) == {
        "guest_management": True
    }
    assert omit_vat(None) == {}


def test_estate_multiplier_uses_type_values(monkeypatch):
    monkeypatch.setattr(
        checkout_mod.settings, "ESTATE_TYPE_HOUSING_MULTIPLIER", 1.0
    )
    monkeypatch.setattr(
        checkout_mod.settings, "ESTATE_TYPE_CORPORATE_MULTIPLIER", 3.0
    )
    assert CheckoutService._estate_multiplier("housing") == 1.0
    assert CheckoutService._estate_multiplier("corporate") == 3.0
    # Postgres/SQLAlchemy may yield the enum name or value.
    assert CheckoutService._estate_multiplier("HOUSING") == 1.0
    assert CheckoutService._estate_multiplier("CORPORATE") == 3.0


def test_estate_multiplier_rejects_missing_and_unknown():
    with pytest.raises(HTTPException) as missing:
        CheckoutService._estate_multiplier(None)
    assert missing.value.status_code == 400

    with pytest.raises(HTTPException) as unknown:
        CheckoutService._estate_multiplier("industrial")
    assert unknown.value.status_code == 400


def test_quote_vat_applied_after_totals():
    quote = quote_pricing(
        service_prices={"guest_management": 100, "administrative_fee": 70},
        ai_prices={},
        included_service_keys=["guest_management", "administrative_fee"],
        ai_feature_keys=[],
        seats=1,
        period_months=1,
        currency_code="NGN",
        country_code="NIGERIA",
    )
    vat = apply_vat(quote["client_total"], "7.5")
    assert quote["client_total"] == Decimal("170.00")
    assert vat["vat_amount"] == Decimal("12.75")
    assert vat["client_total"] == Decimal("182.75")


class _FakeRepo:
    async def get_service_catalog_map(self):
        return {
            "guest_management": {"id": "svc-1"},
            "vat": {"id": "svc-vat"},
        }

    async def get_ai_feature_map(self):
        return {"access_anomaly_detection_tier_1": {"id": "ai-1"}}

    async def get_prices_for_country(self, country):
        return [
            {
                "feature_unit_price": 100,
                "service_catalog_id": "svc-1",
                "currency_code": "NGN",
            },
            {
                "feature_unit_price": 7.5,
                "service_catalog_id": "svc-vat",
                "currency_code": "NGN",
            },
            {
                "feature_unit_price": 5000,
                "ai_feature_id": "ai-1",
                "currency_code": "NGN",
            },
        ]


@pytest.mark.asyncio
async def test_price_maps_scales_unit_prices_but_not_vat():
    svc = CheckoutService(_FakeRepo())
    service_prices, ai_prices, currency, vat_rate = await svc._price_maps(
        "NIGERIA", 3.0
    )
    assert currency == "NGN"
    assert service_prices["guest_management"] == Decimal("300.00")
    assert ai_prices["access_anomaly_detection_tier_1"] == Decimal("15000.00")
    assert vat_rate == 7.5
    assert "vat" not in service_prices


@pytest.mark.asyncio
async def test_price_maps_requires_vat_row():
    async def prices_without_vat(_country):
        return [
            {
                "feature_unit_price": 100,
                "service_catalog_id": "svc-1",
                "currency_code": "NGN",
            }
        ]

    repo = SimpleNamespace(
        get_service_catalog_map=_FakeRepo().get_service_catalog_map,
        get_ai_feature_map=_FakeRepo().get_ai_feature_map,
        get_prices_for_country=prices_without_vat,
    )
    svc = CheckoutService(repo)
    with pytest.raises(HTTPException) as exc:
        await svc._price_maps("NIGERIA", 1.0)
    assert exc.value.status_code == 400
    assert "VAT" in exc.value.detail
