"""
Incident category enum (aligned with db-service ``incident_category``).

Labels are included in TF-IDF documents and counted in paid-tier EDA.
"""

from enum import StrEnum

_ALL = "all"


def drop_all_filter(values: list[str] | str | None) -> list[str] | None:
    """
    Treat ``all`` as unfiltered.

    An omitted list, an empty list, or any ``all`` value (any case)
    means every type is included. Remaining values are lowercased.

    Arguments:
        values: Query values, a single string, or ``None``.

    Returns:
        Lowercased remaining values, or ``None`` when the filter
        should be omitted.
    """
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    if not values:
        return None
    normalized = [str(v).strip().lower() for v in values if str(v).strip()]
    if not normalized or _ALL in normalized:
        return None
    return normalized


class IncidentCategory(StrEnum):
    """Controlled incident categories returned by db-service."""

    SECURITY = "security"
    ACCESS_CONTROL = "access_control"
    NOISE_DISTURBANCE = "noise_disturbance"
    PROPERTY_DAMAGE = "property_damage"
    MAINTENANCE = "maintenance"
    FIRE_SAFETY = "fire_safety"
    MEDICAL_EMERGENCY = "medical_emergency"
    THEFT = "theft"
    HARASSMENT = "harassment"
    DISPUTE = "dispute"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    OTHER = "other"
