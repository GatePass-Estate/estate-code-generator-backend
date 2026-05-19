"""
Feature scopes from the design doc (VS/RS/SS/EW).

These describe *which class of features* is extracted from pulled data, not the
anomaly pipeline type (see app.domain.anomaly_types.AnomalyType).
"""

from enum import StrEnum


class AnalysisScope(StrEnum):
    """Behavioural lens for feature engineering (visitor / resident / security / estate)."""

    VISITOR = "visitor_specific"  # VS — excluded when anomaly_type is resident
    RESIDENT = "resident_specific"  # RS
    SECURITY = "security_specific"  # SS
    ESTATE_WIDE = "estate_wide"  # EW


class TriggerMode(StrEnum):
    """How the pipeline was invoked."""

    REALTIME = "realtime"  # e.g. post-validation Pub/Sub (future)
    BATCH = "batch"  # retrospective / scheduled
