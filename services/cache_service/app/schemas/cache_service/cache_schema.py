from datetime import datetime
from enum import Enum
from typing import List

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

__all__ = [
    "ValidityPeriod",
    "ValidityWindow",
    "VisitorData",
    "CreateRequest",
    "CreateResponse",
    "GetResponse",
    "ExtendResponse",
    "FreezeResponse",
]

# Shared configuration for the pydantic models
model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


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


class Receiver(str, Enum):
    """
    Enumeration of supported receiver: visitor and resident
    """

    VISITOR = "visitor"
    RESIDENT = "resident"


class ValidityPeriod(BaseModel):
    """
    Total validity period for a visitor access code.

    Both bounds are absolute UTC datetimes. ``end`` is mirrored by
    ``valid_until`` on cached records. Neither bound may be more than the
    configured maximum validity horizon (``VISITOR_CODE_MAX_VALIDITY_DAYS``).
    The span from start to end may not exceed
    ``VISITOR_CODE_MAX_PERIOD_LENGTH_DAYS`` (default 7 days).
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

    Both ``start`` and ``end`` must be set for the window to apply.
    Values are UTC time-of-day strings (``HH:MM`` or ``HH:MM:SS``).
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
    Cached visitor access code payload.

    Attributes:
        user_id: Resident who issued the code.
        estate_id: Estate the visit targets.
        visitor_fullname: Visitor name.
        relationship_with_resident: Visitor relationship enum.
        gender: Visitor gender enum.
        hashed_code: Generated access code.
        validity_period: Optional total validity period (UTC datetimes).
        validity_window: Optional daily validity window (time-of-day).
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
    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    validity_period: ValidityPeriod | None = Field(
        default=None,
        description="Optional total validity period (absolute UTC datetimes)",
    )
    validity_window: ValidityWindow | None = Field(
        default=None,
        description="Optional daily validity window (time-of-day only)",
    )

    model_config = model_config


class CreateRequest(BaseModel):
    """
    Request model for caching a visitor access code.

    Attributes:
        hashed_code: Generated access code used as the Redis key.
        visit_data: Visitor metadata and optional validity bounds.
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    visit_data: VisitorData = Field(
        ...,
        description="Pydantic model containing visitor's data",
    )


class CreateResponse(BaseModel):
    """
    Response returned after caching a visitor access code.

    ``valid_until`` mirrors ``validity_period.end``.
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    model_config = model_config


class GetResponse(VisitorData):
    """
    Response returned when validating or fetching a visitor access code.

    Includes lifecycle fields and computed validity flags.
    """

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


class ExtendResponse(BaseModel):
    """
    Response returned after attempting to extend a visitor access code.

    Extension adds one hour to the existing ``validity_period.end`` and may
    only succeed once per code.
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
    """List of active visitor access codes for a resident."""

    items: List[GetResponse] = Field(
        ..., description="Ordered list of table objects"
    )
    model_config = model_config

    @field_validator("items")
    def order_items_by_valid_until_desc(cls, value):
        def parse_valid_until(item):
            valid_until_str = getattr(item, "valid_until", None)
            if valid_until_str is None:
                return datetime.min
            try:
                return datetime.strptime(
                    valid_until_str, "%Y-%m-%d %H:%M:%S.%f%z"
                )
            except Exception:
                return datetime.min

        return sorted(
            value,
            key=parse_valid_until,
            reverse=True,
        )
