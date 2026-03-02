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
    "VisitorData",
    "CreateRequest",
    "CreateResponse",
    "GetResponse",
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


class VisitorData(BaseModel):
    """
    Model for Composer Workflows table.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, partner,
            friend, delivery, taxi, technician
        gender (Gender): Gender: male, female, prefer_not_to_say
        hashed_code (str): Visitor's generated access code.
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

    model_config = model_config


class CreateRequest(BaseModel):
    """
    Base request model to CREATE a record.

    Attributes:
        hashed_code (str): Visitor's generated access code.
        visit_data (VisitorData): Pydantic model containing visitor's data
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
    Base response model to CREATE a record.

    Attributes:
        hashed_code (str): Visitor's generated access code.
        valid_until (str): Timestamp of entry code expiry.
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    model_config = model_config


class GetResponse(VisitorData):
    """
    Base response model to GET a record by hashed code.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, partner,
            friend, delivery, taxi, technician
        gender (Gender): Gender: male, female, prefer_not_to_say.
        hashed_code (str): Visitor's generated access code.
        valid_until (str): Timestamp of entry code expiry.
        is_expired (bool): Flag indicating whether code is expired or not.
        receiver (Receiver): Receiver: visitor or resident.
    """

    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    is_expired: bool = Field(
        ..., description="Flag indicating whether code is expired or not"
    )
    receiver: Receiver = Field(
        ..., description="Receiver: visitor or resident"
    )


class ListResponse(BaseModel):
    """
    Response model to GET the list of items.

    Attributes:
        items: list of table objects
    """

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
                # Use conversion code from context
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
