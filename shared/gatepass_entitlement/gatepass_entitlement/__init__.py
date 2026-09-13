"""Shared revenue-service entitlement checks for GatePass services."""

from gatepass_entitlement.ai import (
    check_ai_feature_allowed,
    is_ai_feature_allowed,
    resolve_incident_entitlements,
)
from gatepass_entitlement.config import settings
from gatepass_entitlement.exceptions import EntitlementDeniedError
from gatepass_entitlement.grants import grant_is_entitled, is_purchased
from gatepass_entitlement.service import (
    assert_seat_available,
    check_service_entitlement,
    fetch_seat_limit,
    fetch_service_entitlement,
    require_service_entitlement,
    resolve_retention_from_date,
)

ACCESS_ANOMALY_DETECTION_TIER_1_KEY = (
    settings.ACCESS_ANOMALY_DETECTION_TIER_1_KEY
)
ACCESS_ANOMALY_DETECTION_TIER_2_KEY = (
    settings.ACCESS_ANOMALY_DETECTION_TIER_2_KEY
)
ACCESS_ANOMALY_DETECTION_TIER_3_KEY = (
    settings.ACCESS_ANOMALY_DETECTION_TIER_3_KEY
)
ADMIN_BROADCAST_KEY = settings.ADMIN_BROADCAST_KEY
ADVANCED_CODE_MANAGEMENT_KEY = settings.ADVANCED_CODE_MANAGEMENT_KEY
EXTENDED_HISTORICAL_RECORD_DEFAULT_DAYS = (
    settings.EXTENDED_HISTORICAL_RECORD_DEFAULT_DAYS
)
EXTENDED_HISTORICAL_RECORD_KEY = settings.EXTENDED_HISTORICAL_RECORD_KEY
GUEST_MANAGEMENT_KEY = settings.GUEST_MANAGEMENT_KEY
INCIDENT_REPORT_KEY = settings.INCIDENT_REPORT_KEY
INCIDENT_REPORT_SUMMARY_TIER_1_KEY = (
    settings.INCIDENT_REPORT_SUMMARY_TIER_1_KEY
)
INCIDENT_REPORT_SUMMARY_TIER_2_KEY = (
    settings.INCIDENT_REPORT_SUMMARY_TIER_2_KEY
)
INCIDENT_REPORT_SUMMARY_TIER_3_KEY = (
    settings.INCIDENT_REPORT_SUMMARY_TIER_3_KEY
)
MAX_ACTIVE_USERS_KEY = settings.MAX_ACTIVE_USERS_KEY

__all__ = [
    "ACCESS_ANOMALY_DETECTION_TIER_1_KEY",
    "ACCESS_ANOMALY_DETECTION_TIER_2_KEY",
    "ACCESS_ANOMALY_DETECTION_TIER_3_KEY",
    "ADMIN_BROADCAST_KEY",
    "ADVANCED_CODE_MANAGEMENT_KEY",
    "EXTENDED_HISTORICAL_RECORD_DEFAULT_DAYS",
    "EXTENDED_HISTORICAL_RECORD_KEY",
    "GUEST_MANAGEMENT_KEY",
    "INCIDENT_REPORT_KEY",
    "INCIDENT_REPORT_SUMMARY_TIER_1_KEY",
    "INCIDENT_REPORT_SUMMARY_TIER_2_KEY",
    "INCIDENT_REPORT_SUMMARY_TIER_3_KEY",
    "MAX_ACTIVE_USERS_KEY",
    "EntitlementDeniedError",
    "assert_seat_available",
    "check_ai_feature_allowed",
    "check_service_entitlement",
    "fetch_seat_limit",
    "fetch_service_entitlement",
    "grant_is_entitled",
    "is_ai_feature_allowed",
    "is_purchased",
    "require_service_entitlement",
    "resolve_incident_entitlements",
    "resolve_retention_from_date",
    "settings",
]
