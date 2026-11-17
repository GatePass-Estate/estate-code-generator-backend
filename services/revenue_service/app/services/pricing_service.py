"""Seat + AI flat pricing engine (pure functions, integer kobo arithmetic)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_UP, Decimal
from typing import Any, Iterable, Mapping


ADMIN_FEE_KEY = "administrative_fee"
VAT_KEY = "vat"
_D100 = Decimal("100")
_D10000 = Decimal("10000")


def omit_vat(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    """Drop ``vat`` from an entitlements/catalog map shown to the FE."""
    return {k: v for k, v in dict(mapping or {}).items() if k != VAT_KEY}


def extract_included_keys(entitlements: Mapping[str, Any]) -> list[str]:
    """Extract service keys with truthy entitlements, excluding VAT."""
    return [
        k
        for k, v in entitlements.items()
        if k != VAT_KEY
        and ((isinstance(v, bool) and v) or (isinstance(v, int) and v > 0))
    ]


def to_int(value: Any) -> int:
    """Coerce a numeric-like value to int (kobo).

    Accepts int, float, Decimal, or numeric strings.  Values that are
    already integers pass through.  Fractional inputs are rounded up
    to the nearest integer.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return int(Decimal(str(value)).to_integral_value(rounding=ROUND_UP))


def apply_vat(amount: int, vat_rate: Any) -> dict[str, Any]:
    """Add VAT to a finished subtotal (kobo).

    ``vat_rate`` is stored as basis points (e.g. 750 = 7.5%).
    The returned ``vat_rate`` is the human-readable percentage.
    """
    subtotal = to_int(amount)
    rate_bps = Decimal(str(vat_rate))
    rate_pct = rate_bps / _D100
    vat_amount = int(
        (Decimal(subtotal) * rate_bps / _D10000).to_integral_value(
            rounding=ROUND_UP
        )
    )
    return {
        "subtotal": subtotal,
        "vat_rate": rate_pct,
        "vat_amount": vat_amount,
        "client_total": subtotal + vat_amount,
    }


def compute_price_per_seat(
    feature_prices: Mapping[str, Any],
    included_service_keys: Iterable[str],
) -> dict[str, Any]:
    """Compute seat price from included product features plus admin fee.

    All prices in ``feature_prices`` are expected to be in kobo (int).
    """
    included = set(included_service_keys)
    line_items: list[dict[str, Any]] = []
    product_sum = 0
    admin_fee = 0

    for key in sorted(included):
        if key not in feature_prices:
            raise ValueError(
                f"Missing feature_unit_price for service_key '{key}'"
            )
        amount = to_int(feature_prices[key])
        if key == ADMIN_FEE_KEY:
            admin_fee = amount
            line_items.append(
                {
                    "key": key,
                    "kind": "administrative_fee",
                    "unit_price": amount,
                }
            )
        else:
            product_sum += amount
            line_items.append(
                {
                    "key": key,
                    "kind": "service",
                    "unit_price": amount,
                }
            )

    price_per_seat = product_sum + admin_fee
    return {
        "sum_of_included_features": product_sum,
        "administrative_fee": admin_fee,
        "price_per_seat": price_per_seat,
        "line_items": line_items,
    }


def compute_ai_monthly(
    ai_prices: Mapping[str, Any],
    ai_feature_keys: Iterable[str],
) -> dict[str, Any]:
    """Sum flat monthly AI feature prices (not x seats). All in kobo."""
    total = 0
    line_items: list[dict[str, Any]] = []
    for key in sorted(set(ai_feature_keys)):
        if key not in ai_prices:
            raise ValueError(
                f"Missing feature_unit_price for ai feature_key '{key}'"
            )
        amount = to_int(ai_prices[key])
        total += amount
        line_items.append({"key": key, "kind": "ai", "unit_price": amount})
    return {
        "ai_price_per_month": total,
        "line_items": line_items,
    }


def compute_client_total(
    *,
    price_per_seat: int,
    seats: int,
    ai_price_per_month: int,
    period_months: int,
) -> dict[str, Any]:
    """client_total = (price_per_seat * seats + ai_monthly) * months"""
    if seats < 0:
        raise ValueError("seats must be >= 0")
    if period_months < 1:
        raise ValueError("period_months must be >= 1")

    pps = to_int(price_per_seat)
    ai = to_int(ai_price_per_month)
    seat_cost = pps * seats
    monthly_subtotal = seat_cost + ai
    client_total = monthly_subtotal * period_months
    return {
        "price_per_seat": pps,
        "seats": seats,
        "ai_price_per_month": ai,
        "monthly_subtotal": monthly_subtotal,
        "period_months": period_months,
        "client_total": client_total,
    }


def quote_pricing(
    *,
    service_prices: Mapping[str, Any],
    ai_prices: Mapping[str, Any],
    included_service_keys: Iterable[str],
    ai_feature_keys: Iterable[str],
    seats: int,
    period_months: int,
    currency_code: str,
    country_code: str,
) -> dict[str, Any]:
    """Build a full quote breakdown from seat and AI pricing inputs."""
    seat = compute_price_per_seat(service_prices, included_service_keys)
    ai = compute_ai_monthly(ai_prices, ai_feature_keys)
    totals = compute_client_total(
        price_per_seat=seat["price_per_seat"],
        seats=seats,
        ai_price_per_month=ai["ai_price_per_month"],
        period_months=period_months,
    )
    return {
        **totals,
        "sum_of_included_features": seat["sum_of_included_features"],
        "administrative_fee": seat["administrative_fee"],
        "currency_code": currency_code,
        "country_code": country_code,
        "line_items": seat["line_items"] + ai["line_items"],
    }


def _ceil_div(a: int, b: int) -> int:
    """Integer ceiling division: -(-a // b)."""
    return -(-a // b)


def compute_seat_proration(
    *,
    period_seat_price: int,
    seats_added: int,
    period_start: datetime,
    period_end: datetime,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """
    Prorate a mid-period seat add for the remainder of the billing period.

    ``period_seat_price`` is the full-period price for one seat
    (``price_per_seat * period_months``) in kobo. AI flats are not
    included.
    """
    if seats_added < 1:
        raise ValueError("seats_added must be >= 1")

    start = period_start
    end = period_end
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    else:
        end = end.astimezone(timezone.utc)
    now = as_of or datetime.now(tz=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    period_days = (end.date() - start.date()).days + 1
    if period_days < 1:
        raise ValueError("period_end must be on or after period_start")

    remaining_days = (end.date() - now.date()).days + 1
    if remaining_days < 0:
        remaining_days = 0
    if remaining_days > period_days:
        remaining_days = period_days

    psp = to_int(period_seat_price)
    daily_seat_rate = _ceil_div(psp, period_days)
    prorated_charge = daily_seat_rate * remaining_days * seats_added
    return {
        "period_seat_price": psp,
        "seats_added": seats_added,
        "period_days": period_days,
        "remaining_days": remaining_days,
        "daily_seat_rate": daily_seat_rate,
        "prorated_charge": prorated_charge,
    }


def prorate_tier_change(
    *,
    old_price_per_seat: int,
    new_price_per_seat: int,
    covered_users: int,
    period_months: int,
    period_start: datetime,
    period_end: datetime,
    currency_code: str,
    country_code: str,
    old_ai_monthly: int = 0,
    new_ai_monthly: int = 0,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """
    Compute the prorated charge for an immediate mid-period tier upgrade.

    Compares total monthly cost (seat cost + AI flat) between old and new
    tiers. Raises ValueError when the new tier's total monthly cost does
    not exceed the old tier's (use schedule-tier-change for downgrades).

    Seat-based and AI-based differences are prorated separately so that
    seat rounding behaviour is preserved from the original per-seat logic.
    All amounts are in kobo (int).
    """
    old_pps = to_int(old_price_per_seat)
    new_pps = to_int(new_price_per_seat)
    old_ai = to_int(old_ai_monthly)
    new_ai = to_int(new_ai_monthly)

    old_monthly = old_pps * covered_users + old_ai
    new_monthly = new_pps * covered_users + new_ai

    if new_monthly <= old_monthly:
        raise ValueError(
            "New tier total monthly cost must exceed the old tier's for an "
            "upgrade; use schedule-tier-change for downgrades"
        )

    # Prorate seat difference (per-seat x covered_users)
    diff_per_seat = new_pps - old_pps
    period_seat_price = diff_per_seat * period_months

    seat_proration = compute_seat_proration(
        period_seat_price=period_seat_price,
        seats_added=covered_users,
        period_start=period_start,
        period_end=period_end,
        as_of=as_of,
    )

    # Prorate AI difference (flat monthly, not per-seat)
    ai_diff = new_ai - old_ai
    ai_prorated = 0
    if ai_diff > 0:
        ai_period_price = ai_diff * period_months
        ai_proration = compute_seat_proration(
            period_seat_price=ai_period_price,
            seats_added=1,
            period_start=period_start,
            period_end=period_end,
            as_of=as_of,
        )
        ai_prorated = ai_proration["prorated_charge"]

    subtotal = seat_proration["prorated_charge"] + ai_prorated
    return {
        **seat_proration,
        "old_price_per_seat": old_pps,
        "new_price_per_seat": new_pps,
        "old_ai_monthly": old_ai,
        "new_ai_monthly": new_ai,
        "ai_prorated_charge": ai_prorated,
        "tier_diff_per_seat": diff_per_seat,
        "covered_users": covered_users,
        "period_months": period_months,
        "currency_code": currency_code,
        "country_code": country_code,
        "subtotal": subtotal,
    }
