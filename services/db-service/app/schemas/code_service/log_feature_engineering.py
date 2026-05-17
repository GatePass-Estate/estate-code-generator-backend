"""Schemas and enums for persisted per-scope feature vectors."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import UUID4, BaseModel, Field, model_validator

from app.schemas.base import model_config


class AnomalyType(StrEnum):
    """Visitor- vs resident-centred pipeline.

    Uses the same values as ai-service.
    """

    VISITOR = "visitor"
    RESIDENT = "resident"


class LogKind(StrEnum):
    """Visitor vs resident log row ids (``visitorlog`` / ``residentlog``)."""

    VISITOR = "visitor"
    RESIDENT = "resident"


class PredictionType(StrEnum):
    """Prediction classes persisted in ``core.predictionresult``.

    Expand this enum as new prediction producers are introduced.
    """

    VISITOR_ANOMALY_REALTIME = "VisitorAnomalyRealtime"
    RESIDENT_ANOMALY_REALTIME = "ResidentAnomalyRealtime"


class BatchLookupRequest(BaseModel):
    """Fetch stored feature rows for prior log validations."""

    model_config = model_config

    log_ids: list[UUID4] = Field(
        ...,
        description="Log row ids (visitor or resident table per log_kind).",
    )
    anomaly_type: AnomalyType = Field(
        ...,
        description="Anomaly pipeline that produced the stored vectors.",
    )
    log_kind: LogKind = Field(
        ...,
        description="Filter by visitor_log_id vs resident_log_id.",
    )


class StoredFeatureRecord(BaseModel):
    """One persisted row (all scopes that were stored)."""

    model_config = model_config

    id: UUID4
    visitor_log_id: UUID4 | None = None
    resident_log_id: UUID4 | None = None
    anomaly_type: AnomalyType
    log_kind: LogKind
    features_visitor_specific: dict[str, Any] | None = None
    features_resident_specific: dict[str, Any] | None = None
    features_security_specific: dict[str, Any] | None = None
    features_estate_wide: dict[str, Any] | None = None
    is_anomalous: bool = Field(
        default=False,
        description=(
            "True if this snapshot was from a validation flagged anomalous."
        ),
    )


class BatchLookupResponse(BaseModel):
    """Rows found for the requested ids (may omit never-engineered logs)."""

    model_config = model_config

    items: list[StoredFeatureRecord]


class UpsertRequest(BaseModel):
    """Create or update the feature snapshot for one log validation."""

    model_config = model_config

    visitor_log_id: UUID4 | None = None
    resident_log_id: UUID4 | None = None
    anomaly_type: AnomalyType
    log_kind: LogKind
    features_visitor_specific: dict[str, Any] | None = None
    features_resident_specific: dict[str, Any] | None = None
    features_security_specific: dict[str, Any] | None = None
    features_estate_wide: dict[str, Any] | None = None
    is_anomalous: bool | None = Field(
        default=None,
        description=(
            "Set when persisting after scoring; omit to leave unchanged "
            "on update."
        ),
    )
    prediction_type: PredictionType | None = Field(
        default=None,
        description=("Prediction classifier label (enum-backed in database)."),
    )
    prediction_result: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Prediction payload JSON; usually {'result': <analysis_output>}."
        ),
    )

    @model_validator(mode="after")
    def anchor_and_log_kind(self) -> UpsertRequest:
        v, r = self.visitor_log_id, self.resident_log_id
        if (v is None) == (r is None):
            raise ValueError(
                "Provide exactly one of visitor_log_id or resident_log_id."
            )
        if v is not None and self.log_kind != LogKind.VISITOR:
            raise ValueError(
                "log_kind must be visitor when visitor_log_id is set."
            )
        if r is not None and self.log_kind != LogKind.RESIDENT:
            raise ValueError(
                "log_kind must be resident when resident_log_id is set."
            )
        if (self.prediction_type is None) != (self.prediction_result is None):
            raise ValueError(
                "prediction_type and prediction_result must be "
                "provided together."
            )
        return self


class UpsertResponse(BaseModel):
    """Echo the stored row id after upsert."""

    model_config = model_config

    id: UUID4
