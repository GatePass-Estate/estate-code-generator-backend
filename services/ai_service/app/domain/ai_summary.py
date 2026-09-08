"""Shared lookup-key helpers for the ``core.ai_response`` cache."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

ANOMALY_SUMMARY_FEATURE_KEY = "visitor_resident_anomaly_detection"
INCIDENT_SUMMARY_FEATURE_KEY = "incident_summary_basic"
INCIDENT_SUMMARY_TIER2_KEY = "incident_summary_basic_tier2"
INCIDENT_SUMMARY_TIER3_KEY = "incident_summary_basic_tier3"

_OPEN = "open"


def anomaly_lookup_key(prediction_id: UUID | str) -> str:
    """
    Build the ``ai_response`` lookup key for one prediction.

    Arguments:
        prediction_id: Prediction-result id.

    Returns:
        The id as a string.
    """
    return str(prediction_id)


def _iso(dt: datetime | None) -> str:
    """
    Format a bound as UTC ISO-8601 with a trailing Z.

    Arguments:
        dt: Inclusive window bound, or ``None`` when open.

    Returns:
        A ``...Z`` timestamp, or ``open``.
    """
    if dt is None:
        return _OPEN
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def incident_lookup_key(
    estate_id: UUID | str,
    from_date: datetime | None,
    to_date: datetime | None,
) -> str:
    """
    Build the ``ai_response`` lookup key for one estate window.

    Arguments:
        estate_id: Estate whose summaries are cached.
        from_date: Inclusive lower bound, or ``None`` for open.
        to_date: Inclusive upper bound, or ``None`` for open.

    Returns:
        ``{estate_id}:{from}:{to}`` with ``open`` for missing bounds.
    """
    return f"{estate_id}:{_iso(from_date)}:{_iso(to_date)}"
