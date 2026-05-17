"""
Incident category enum (aligned with db-service ``incident_category``).

Labels are included in TF-IDF documents and counted in paid-tier EDA.
"""

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
