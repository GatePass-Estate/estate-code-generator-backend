from enum import Enum

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
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


class VisitorData(BaseModel):
    """
    Model for Composer Workflows table.

    Attributes:
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, partner,
            friend, delivery, taxi, technician
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
    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )

    model_config = model_config


class CreateRequest(BaseModel):
    """
    Base request model to CREATE a record.

    Attributes:
        hashed_code (str): Visitor's generated access code.
        visit_data (UUID): Security personnel who validated the visit
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
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
    """

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    model_config = model_config


class GetResponse(VisitorData):
    """
    Base response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        user_id (UUID): Reference to the visited resident.
        estate_id (UUID): Reference to the visited estate.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, partner,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """

    valid_until: str = Field(..., description="Timestamp of entry code expiry")
    is_expired: bool = Field(
        ..., description="Flag indicating whether code is expired or not"
    )
