"""Serialize helpers for spatial analyze / prediction-result payloads."""

from __future__ import annotations

from typing import Any

PAYLOAD_FLOAT_DECIMALS = 2


def round_payload_floats(
    value: Any, *, ndigits: int = PAYLOAD_FLOAT_DECIMALS
) -> Any:
    """
    Recursively round ``float`` leaves in dict/list structures.

    Integers, strings, booleans, and ``None`` are left unchanged so counts
    and flags in transparency payloads stay exact.
    """
    if isinstance(value, float):
        return round(value, ndigits)
    if isinstance(value, dict):
        return {
            str(k): round_payload_floats(v, ndigits=ndigits)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [round_payload_floats(v, ndigits=ndigits) for v in value]
    return value
