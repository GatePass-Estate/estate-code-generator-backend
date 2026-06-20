from enum import Enum
from typing import List

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
)

__all__ = [
    "ValidityPeriod",
    "ValidityWindow",
    "VisitorData",
    "ResidentData",
    "CreateRequestVisitor",
    "CreateRequestResident",
    "CreateResponse",
    "GetResponseVisitor",
    "GetResponseResident",
    "ExtendResponse",
    "FreezeResponse",
]

# Shared configuration for the pydantic models
model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class Receiver(str, Enum):
    """
    Enumeration of supported receiver: visitor and resident
    """

    VISITOR = "visitor"
    RESIDENT = "resident"


class Relation(str, Enum):
    """
    Enumeration of supported resident-guest relation: family, partner,
            friend, delivery, taxi, technician
    """

    FAMILY = "family"
    PARTNER = "partner"
    FRIEND = "friend"
    TECHNICIAN = "technician"
    TAXI = "taxi"
    DELIVERY = "delivery"
    OTHER = "other"


class Gender(str, Enum):
    """
    Enumeration of supported gender: male, female
    """

    MALE = "male"
    FEMALE = "female"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class ValidityPeriod(BaseModel):
    """
    Total validity period for a visitor access code.

    Optional on create; defaults to one hour from creation when omitted.
    Neither bound may be more than 2 weeks from the current time.
    """

    start: str | None = Field(
        default=None, description="Total validity period start (UTC datetime)"
    )
    end: str | None = Field(
        default=None, description="Total validity period end (UTC datetime)"
    )

    model_config = model_config


class ValidityWindow(BaseModel):
    """
    Daily validity window for a visitor access code.

    Both bounds must be provided for the window to apply.
    """

    start: str | None = Field(
        default=None, description="Daily window start (HH:MM or HH:MM:SS)"
    )
    end: str | None = Field(
        default=None, description="Daily window end (HH:MM or HH:MM:SS)"
    )

    model_config = model_config


class VisitorData(BaseModel):
    """
    Base visitor fields shared across create and validate responses.

    Attributes:
        user_id: Resident who issued the code.
        estate_id: Estate the visit targets.
        visitor_fullname: Visitor name.
        relationship_with_resident: Visitor relationship enum.
        gender: Visitor gender enum.
    """

    user_id: UUID4 = Field(
        ..., description="Reference to the visited resident"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 = Field(
        ..., description="Reference to the visited estate"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    visitor_fullname: str = Field(..., description="Full name of the visitor")
    relationship_with_resident: Relation = Field(
        ...,
        description="Relation: family, partner, friend, delivery, taxi, etc",
    )
    gender: Gender = Field(
        ...,
        description="Gender: male, female, prefer_not_to_say",
    )

    model_config = model_config


class ResidentData(BaseModel):
    """Base resident fields for resident access codes."""

    user_id: UUID4 = Field(
        ..., description="Reference to the visited resident"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 = Field(
        ..., description="Reference to the visited estate"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class CreateRequestVisitor(VisitorData):
    """
    Request body for generating a visitor access code.

    ``validity_period`` sets the total active range (UTC datetimes) and may
    not start or end more than 2 weeks from the current time.
    ``validity_window`` restricts usage to daily hours (time-of-day).
    Both are optional; omitted period defaults to one hour from creation.
    """

    validity_period: ValidityPeriod | None = Field(
        default=None,
        description="Optional total validity period (absolute UTC datetimes)",
    )
    validity_window: ValidityWindow | None = Field(
        default=None,
        description="Optional daily validity window (time-of-day only)",
    )


class CreateRequestResident(ResidentData):
    """Request body for generating a resident access code."""


class CreateResponse(BaseModel):
    """Response returned after generating an access code."""

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    model_config = model_config


class GetResponseVisitor(VisitorData):
    """
    Response returned when validating a visitor access code.

    Includes lifecycle fields and computed ``is_valid`` / ``is_expired``.
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    validity_period: ValidityPeriod = Field(
        ..., description="Total validity period (absolute UTC datetimes)"
    )
    validity_window: ValidityWindow | None = Field(
        default=None, description="Daily validity window (time-of-day)"
    )
    extended: bool = Field(
        default=False, description="Whether the code has been extended"
    )
    frozen: bool = Field(
        default=False, description="Whether the code is frozen/paused"
    )
    is_expired: bool = Field(
        ..., description="Flag indicating whether code is expired or not"
    )
    is_valid: bool = Field(
        ..., description="Whether the code passes all validity checks"
    )
    receiver: Receiver = Field(
        ..., description="Receiver: visitor or resident"
    )


class GetResponseResident(ResidentData):
    """Response returned when validating a resident access code."""

    hashed_code: str = Field(
        ..., description="Resident's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    is_expired: bool = Field(
        ..., description="Flag indicating whether code is expired or not"
    )
    is_valid: bool = Field(
        ..., description="Whether the code passes all validity checks"
    )
    receiver: Receiver = Field(
        ..., description="Receiver: visitor or resident"
    )


class ExtendResponse(BaseModel):
    """
    Response returned after attempting to extend a visitor access code.

    Extension adds one hour to the existing total period end and can only
    succeed once per code.
    """

    success: bool = Field(..., description="Whether the extension succeeded")
    hashed_code: str = Field(..., description="Visitor's access code")
    valid_until: str = Field(..., description="Updated expiry timestamp")
    validity_period: ValidityPeriod = Field(
        ..., description="Updated total validity period"
    )
    extended: bool = Field(..., description="Whether the code is now extended")
    message: str | None = Field(
        default=None, description="Optional failure or status message"
    )

    model_config = model_config


class FreezeResponse(BaseModel):
    """Response returned after toggling freeze on a visitor access code."""

    hashed_code: str = Field(..., description="Visitor's access code")
    frozen: bool = Field(..., description="Current frozen state")
    is_valid: bool = Field(
        ..., description="Whether the code is valid after the toggle"
    )

    model_config = model_config


class ListResponse(BaseModel):
    """List of visitor access codes issued by a resident."""

    items: List[GetResponseVisitor] = Field(
        ..., description="Ordered list of table objects"
    )
    model_config = model_config
