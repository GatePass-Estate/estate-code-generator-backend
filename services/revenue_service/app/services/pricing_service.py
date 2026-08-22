"""Seat + AI flat pricing engine (pure functions)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Mapping


ADMIN_FEE_KEY = "administrative_fee"


def _to_decimal(value: Any) -> Decimal:
    """
    Coerce a numeric-like value to Decimal.

    Args:
        value: Decimal, int, float, or string amount.

    Returns:
        Decimal representation of value.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_price_per_seat(
    feature_prices: Mapping[str, Any],
    included_service_keys: Iterable[str],
) -> dict[str, Any]:
    """
    Compute seat price from included product features plus admin fee.

    price_per_seat = sum(product features excluding administrative_fee)
                     + administrative_fee

    Args:
        feature_prices: Map of service_key -> unit price.
        included_service_keys: Service keys included in the quote.

    Returns:
        Breakdown with sum_of_included_features, administrative_fee,
        price_per_seat, and line_items.

    Raises:
        ValueError: If a required service_key has no unit price.
    """
    included = set(included_service_keys)
    line_items: list[dict[str, Any]] = []
    product_sum = Decimal("0")
    admin_fee = Decimal("0")

    for key in sorted(included):
        if key not in feature_prices:
            raise ValueError(
                f"Missing feature_unit_price for service_key '{key}'"
            )
        amount = _to_decimal(feature_prices[key])
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

    # Admin fee always applied when priced (even if not in included keys,
    # callers should include it for paid tiers). If present in prices map
    # but not included, do not add.
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
    """
    Sum flat monthly AI feature prices (not × seats).

    Args:
        ai_prices: Map of AI feature_key -> monthly unit price.
        ai_feature_keys: AI feature keys included in the quote.

    Returns:
        Dict with ai_price_per_month and line_items.

    Raises:
        ValueError: If a required AI feature_key has no unit price.
    """
    total = Decimal("0")
    line_items: list[dict[str, Any]] = []
    for key in sorted(set(ai_feature_keys)):
        if key not in ai_prices:
            raise ValueError(
                f"Missing feature_unit_price for ai feature_key '{key}'"
            )
        amount = _to_decimal(ai_prices[key])
        total += amount
        line_items.append({"key": key, "kind": "ai", "unit_price": amount})
    return {"ai_price_per_month": total, "line_items": line_items}


def compute_client_total(
    *,
    price_per_seat: Any,
    seats: int,
    ai_price_per_month: Any,
    period_months: int,
) -> dict[str, Any]:
    """
    Compute the client total for a billing period.

    client_total = (price_per_seat * seats + ai_monthly) * months

    Args:
        price_per_seat: Per-seat monthly price.
        seats: Number of covered users / seats.
        ai_price_per_month: Flat AI monthly add-on total.
        period_months: Billing period length in months.

    Returns:
        Totals breakdown including monthly_subtotal and client_total.

    Raises:
        ValueError: If seats < 0 or period_months < 1.
    """
    if seats < 0:
        raise ValueError("seats must be >= 0")
    if period_months < 1:
        raise ValueError("period_months must be >= 1")

    pps = _to_decimal(price_per_seat)
    ai = _to_decimal(ai_price_per_month)
    seat_cost = pps * Decimal(seats)
    monthly_subtotal = seat_cost + ai
    client_total = monthly_subtotal * Decimal(period_months)
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
    """
    Build a full quote breakdown from seat and AI pricing inputs.

    Args:
        service_prices: Map of service_key -> unit price.
        ai_prices: Map of AI feature_key -> monthly unit price.
        included_service_keys: Product service keys included in the seat price.
        ai_feature_keys: AI features included as flat monthly add-ons.
        seats: Number of covered users / seats.
        period_months: Billing period length in months.
        currency_code: Currency for the quote (e.g. NGN).
        country_code: Country used to select prices.

    Returns:
        Full quote dict with totals, fees, currency, and line_items.

    Raises:
        ValueError: If pricing inputs are invalid or prices are missing.
    """
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
