"""Validate entitlements JSONB maps against service_catalog limit types."""

from __future__ import annotations

from typing import Any, Mapping

from app.services.pricing_service import ADMIN_FEE_KEY

__all__ = ["ensure_admin_fee_entitlement", "validate_entitlements"]


def ensure_admin_fee_entitlement(
    entitlements: Mapping[str, Any],
    *,
    default: bool = True,
) -> dict[str, Any]:
    """
    Ensure ``administrative_fee`` is present on a custom entitlements map.

    Custom snapshots may omit the key; default it (True for paid custom) so
    pricing and entitlement checks always see an explicit boolean.
    Does not overwrite an existing value.
    """
    out = dict(entitlements)
    if ADMIN_FEE_KEY not in out:
        out[ADMIN_FEE_KEY] = default
    return out


def validate_entitlements(
    entitlements: Mapping[str, Any],
    service_catalog: Mapping[str, str],
) -> dict[str, Any]:
    """
    Validate an entitlements map against a service_catalog key -> limit_type map.

    Args:
        entitlements: Mapping of service_key -> entitlement value.
        service_catalog: Mapping of service_key -> limit_type
            (boolean | int | count | duration_days).

    Returns:
        The validated entitlements dict (unchanged keys/values).

    Raises:
        ValueError: If a key is unknown or a value has the wrong type/range.
    """
    if entitlements is None:
        raise ValueError("entitlements must be a mapping")
    if not isinstance(entitlements, Mapping):
        raise ValueError("entitlements must be a mapping")

    validated: dict[str, Any] = {}
    for key, value in entitlements.items():
        if key not in service_catalog:
            raise ValueError(
                f"Unknown entitlement key '{key}'; "
                "not present in service_catalog"
            )
        limit_type = service_catalog[key]
        if limit_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(
                    f"Entitlement '{key}' requires a boolean value, "
                    f"got {type(value).__name__}"
                )
        elif limit_type in ("int", "count", "duration_days"):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"Entitlement '{key}' requires an int >= 0 "
                    f"(limit_type={limit_type}), got {type(value).__name__}"
                )
            if value < 0:
                raise ValueError(
                    f"Entitlement '{key}' must be >= 0, got {value}"
                )
        else:
            raise ValueError(
                f"Unknown limit_type '{limit_type}' for service_key '{key}'"
            )
        validated[key] = value
    return validated
