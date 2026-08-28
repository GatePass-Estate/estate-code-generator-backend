"""Seat + AI flat pricing engine (pure functions)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_UP, Decimal
from typing import Any, Iterable, Mapping


ADMIN_FEE_KEY = "administrative_fee"
MONEY_QUANT = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    """Coerce a numeric-like value to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_charge(amount: Any) -> Decimal:
    """Round a billable total up to two decimal places."""
    return _to_decimal(amount).quantize(MONEY_QUANT, rounding=ROUND_UP)


def compute_price_per_seat(
    feature_prices: Mapping[str, Any],
    included_service_keys: Iterable[str],
) -> dict[str, Any]:
    """Compute seat price from included product features plus admin fee."""
    included = set(included_service_keys)
    line_items: list[dict[str, Any]] = []
    product_sum = Decimal("0")
    admin_fee = Decimal("0")

    for key in sorted(included):
        if key not in feature_prices:
            raise ValueError(
                f"Missing feature_unit_price for service_key '{key}'"
            )
        amount = round_charge(_to_decimal(feature_prices[key]))
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

    price_per_seat = round_charge(product_sum + admin_fee)
    return {
        "sum_of_included_features": round_charge(product_sum),
        "administrative_fee": round_charge(admin_fee),
        "price_per_seat": price_per_seat,
        "line_items": line_items,
    }


def compute_ai_monthly(
    ai_prices: Mapping[str, Any],
    ai_feature_keys: Iterable[str],
) -> dict[str, Any]:
    """Sum flat monthly AI feature prices (not × seats)."""
    total = Decimal("0")
    line_items: list[dict[str, Any]] = []
    for key in sorted(set(ai_feature_keys)):
        if key not in ai_prices:
            raise ValueError(
                f"Missing feature_unit_price for ai feature_key '{key}'"
            )
        amount = round_charge(_to_decimal(ai_prices[key]))
        total += amount
        line_items.append({"key": key, "kind": "ai", "unit_price": amount})
    return {
        "ai_price_per_month": round_charge(total),
        "line_items": line_items,
    }


def compute_client_total(
    *,
    price_per_seat: Any,
    seats: int,
    ai_price_per_month: Any,
    period_months: int,
) -> dict[str, Any]:
    """client_total = (price_per_seat * seats + ai_monthly) * months"""
    if seats < 0:
        raise ValueError("seats must be >= 0")
    if period_months < 1:
        raise ValueError("period_months must be >= 1")

    pps = round_charge(price_per_seat)
    ai = round_charge(ai_price_per_month)
    seat_cost = pps * Decimal(seats)
    monthly_subtotal = round_charge(seat_cost + ai)
    client_total = round_charge(monthly_subtotal * Decimal(period_months))
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


def compute_seat_proration(
    *,
    period_seat_price: Any,
    seats_added: int,
    period_start: datetime,
    period_end: datetime,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """
    Prorate a mid-period seat add for the remainder of the billing period.

    ``period_seat_price`` is the full-period price for one seat
    (``price_per_seat × period_months``). AI flats are not included.
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

    psp = round_charge(period_seat_price)
    daily_seat_rate = round_charge(psp / Decimal(period_days))
    prorated_charge = round_charge(
        daily_seat_rate * Decimal(remaining_days) * Decimal(seats_added)
    )
    return {
        "period_seat_price": psp,
        "seats_added": seats_added,
        "period_days": period_days,
        "remaining_days": remaining_days,
        "daily_seat_rate": daily_seat_rate,
        "prorated_charge": prorated_charge,
    }
