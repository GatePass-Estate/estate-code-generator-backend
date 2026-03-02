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
    "VisitorData",
    "ResidentData",
    "CreateRequestVisitor",
    "CreateRequestResident",
    "CreateResponse",
    "GetResponseVisitor",
    "GetResponseResident",
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
    """
    Model for Composer Workflows table.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
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

    model_config = model_config


class CreateRequestVisitor(VisitorData):
    """
    Base request model to CREATE a record.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, partner,
            friend, delivery, taxi, technician
    """


class CreateRequestResident(ResidentData):
    """
    Base request model to CREATE a record.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a record.

    Attributes:
        hashed_code (str): Visitor's generated access code.
        valid_until (DateTime): Timestamp of entry code expiry
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    model_config = model_config


class GetResponseVisitor(VisitorData):
    """
    Base response model to GET a record by id.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, partner,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        valid_until (DateTime): Timestamp of entry code expiry
        is_expired (bool): Flag indicating whether code is expired or not
        receiver (Receiver): Receiver: visitor or resident.
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    is_expired: bool = Field(
        ..., description="Flag indicating whether code is expired or not"
    )
    receiver: Receiver = Field(
        ..., description="Receiver: visitor or resident"
    )


class GetResponseResident(ResidentData):
    """
    Base response model to GET a record by id.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        hashed_code (str): Resident's generated access code.
        valid_until (DateTime): Timestamp of entry code expiry
        is_expired (bool): Flag indicating whether code is expired or not
        receiver (Receiver): Receiver: visitor or resident.
    """

    hashed_code: str = Field(
        ..., description="Resident's generated access code"
    )
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

    items: List[GetResponseVisitor] = Field(
        ..., description="Ordered list of table objects"
    )
    model_config = model_config
