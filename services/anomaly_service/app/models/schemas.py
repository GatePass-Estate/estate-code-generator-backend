"""Pydantic request/response models for the anomaly service API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import UUID4, BaseModel, ConfigDict, Field, model_validator

from app.domain.scopes import TriggerMode


class Receiver(StrEnum):
    """Mirrors code-service `Receiver` on validation GET responses."""

    VISITOR = "visitor"
    RESIDENT = "resident"


class CodeValidationPayload(BaseModel):
    """
    Aligns with code-service GET ``/validate/{code}`` responses plus log-anchor
    fields.

    ``validated_user_id`` is the resident who **issued the visitor code**
    (host) or **owns the resident access code** under validation. ``user_id``
    is the resident on the code-service record (often the same id).
    ``security_id`` scopes db-service log search to that security user.
    """

    model_config = ConfigDict(extra="ignore")

    validated_user_id: UUID4 = Field(
        ...,
        description=(
            "Resident who generated the visitor code or owns the access code "
            "being validated."
        ),
    )
    security_id: UUID4 = Field(
        ...,
        description="Security user id; filters visitor/resident log search.",
    )
    user_id: UUID4 = Field(
        ...,
        description=(
            "Resident on the validation record (often matches "
            "validated_user_id)."
        ),
    )
    estate_id: UUID4
    hashed_code: str
    valid_until: str
    is_expired: bool
    receiver: Receiver
    visitor_log_id: UUID4 | None = Field(
        default=None,
        description="Anchor row in visitorlog; mutually exclusive with "
        "resident_log_id.",
    )
    resident_log_id: UUID4 | None = Field(
        default=None,
        description="Anchor row in residentlog; mutually exclusive with "
        "visitor_log_id.",
    )
    visitor_fullname: str | None = None
    relationship_with_resident: str | None = None
    gender: str | None = None

    @model_validator(mode="after")
    def exactly_one_log_and_receiver_alignment(self) -> CodeValidationPayload:
        v, r = self.visitor_log_id, self.resident_log_id
        if (v is None) == (r is None):
            raise ValueError(
                "Provide exactly one of visitor_log_id or resident_log_id."
            )
        if v is not None and self.receiver != Receiver.VISITOR:
            raise ValueError(
                "visitor_log_id requires receiver=visitor on the payload."
            )
        if r is not None and self.receiver != Receiver.RESIDENT:
            raise ValueError(
                "resident_log_id requires receiver=resident on the payload."
            )
        return self


class AnalyzeRequest(BaseModel):
    """Code validation outcome; ``trigger`` is metadata only for now."""

    code_validation: CodeValidationPayload
    trigger: TriggerMode = TriggerMode.REALTIME


class FeatureContribution(BaseModel):
    feature_name: str
    value: float
    weight: float | None = None
    contribution: float | None = None


class ScopeTransparencyDetail(BaseModel):
    scope: str
    score: float
    feature_contributions: list[FeatureContribution]
    thresholds: dict[str, float] = Field(default_factory=dict)
    model_ids: list[str] = Field(default_factory=list)
    model_outputs: dict[str, float] = Field(default_factory=dict)


class AnalysisTransparency(BaseModel):
    """Structured transparency for audit and UI (scores, features, models)."""

    scopes: list[ScopeTransparencyDetail]
    ensemble_method: str
    ensemble_notes: str | None = None
    global_model_outputs: dict[str, float] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    final_score: float
    per_scope_scores: dict[str, float]
    explanation: str
    scopes_evaluated: list[str]
    anomaly_type: str
    transparency: AnalysisTransparency
