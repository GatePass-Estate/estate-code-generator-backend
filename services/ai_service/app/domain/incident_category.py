"""Incident taxonomy values (aligned with db-service ``IncidentCategory``)."""

from enum import StrEnum


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
