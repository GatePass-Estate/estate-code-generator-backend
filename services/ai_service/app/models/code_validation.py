"""Shared code-validation request models for spatial and temporal anomaly APIs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    UUID4,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.scopes import TriggerMode


class Receiver(StrEnum):
    """Mirrors code-service `Receiver` on validation GET responses."""

    VISITOR = "visitor"
    RESIDENT = "resident"


class CodeValidationPayload(BaseModel):
    """
    Aligns with code-service GET ``/validate/{code}`` responses plus log-anchor
    fields.

    ``user_id`` is the resident who issued the visitor code or owns the resident
    access record. Upstream may label this ``validated_user_id``; either JSON
    key is accepted on input.
    ``security_id`` scopes db-service log search to that security user.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_id: UUID4 = Field(
        ...,
        validation_alias=AliasChoices("user_id", "validated_user_id"),
        description=(
            "Resident who issued the visitor code or owns the resident access "
            "record (code-service may send this as ``validated_user_id``)."
        ),
    )
    security_id: UUID4 = Field(
        ...,
        description="Security user id; filters visitor/resident log search.",
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
        """Require one log anchor and align ``receiver`` with its log type."""
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
