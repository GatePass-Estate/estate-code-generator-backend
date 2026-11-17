"""Schemas for the shared AI-response cache."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import model_config

# Catalog keys that own a row in ``core.ai_response``.
ANOMALY_SUMMARY_FEATURE_KEY = "visitor_resident_anomaly_detection"
INCIDENT_SUMMARY_FEATURE_KEY = "incident_summary_basic"


def _tier_present(raw: Any, key: str) -> bool:
    """True when ``ai_summary[key]`` is a non-empty cached report."""
    if not isinstance(raw, dict):
        return False
    value = raw.get(key)
    if value is None or value == "" or value == {}:
        return False
    return True


def _as_summary(raw: Any) -> dict[str, Any] | None:
    """Return the stored JSON object, or None if empty."""
    return raw if isinstance(raw, dict) and raw else None


class GetRequest(BaseModel):
    """Lookup one cached response by feature key and unique lookup key."""

    model_config = model_config

    feature_key: str = Field(..., min_length=1)
    lookup_key: str = Field(..., min_length=1)


class UpsertRequest(BaseModel):
    """Insert or merge tier payloads into ``ai_summary`` for one lookup key."""

    model_config = model_config

    feature_key: str = Field(..., min_length=1)
    lookup_key: str = Field(..., min_length=1)
    prediction_result_id: UUID4 | None = None
    estate_id: UUID4 | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    tier1: dict[str, Any] | None = None
    tier2: dict[str, Any] | None = None

    @field_serializer("prediction_result_id", "estate_id")
    def serialize_optional_uuid(self, value: UUID4 | None) -> str | None:
        """Emit optional UUID fields as strings."""
        return str(value) if value is not None else None


class GetResponse(BaseModel):
    """Stored ``ai_summary`` JSON plus presence flags for one cache row."""

    model_config = model_config

    id: UUID4
    feature_key: str
    lookup_key: str
    prediction_result_id: UUID4 | None = None
    estate_id: UUID4 | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    ai_summary: dict[str, Any] | None = None
    has_tier1_summary: bool = False
    has_tier2_summary: bool = False

    @field_serializer("id", "prediction_result_id", "estate_id")
    def serialize_optional_uuid(self, value: UUID4 | None) -> str | None:
        """Emit UUID fields as strings."""
        return str(value) if value is not None else None


def to_response(record) -> GetResponse:
    """Map an ``AiResponse`` ORM row onto ``GetResponse``."""
    summary = _as_summary(record.ai_summary)
    return GetResponse(
        id=record.id,
        feature_key=record.feature_key,
        lookup_key=record.lookup_key,
        prediction_result_id=record.prediction_result_id,
        estate_id=record.estate_id,
        from_date=record.from_date,
        to_date=record.to_date,
        ai_summary=summary,
        has_tier1_summary=_tier_present(summary, "tier1"),
        has_tier2_summary=_tier_present(summary, "tier2"),
    )
