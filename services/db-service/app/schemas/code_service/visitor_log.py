from datetime import datetime
from enum import Enum
from typing import List

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.code_service.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class Relation(str, Enum):
    """
    Enumeration of supported resident-guest relation: family, spouse,
            friend, delivery, taxi, technician
    """

    FAMILY = "family"
    SPOUSE = "spouse"
    FRIEND = "friend"
    TECHNICIAN = "technician"
    TAXI = "taxi"
    DELIVERY = "delivery"


class VisitorLogBase(BaseModel):
    """
    Model for Composer Workflows table.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        user_id (UUID): Reference to the visited resident.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, spouse,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """

    user_id: UUID4 = Field(
        ..., description="Reference to the visited resident"
    )
    visitor_fullname: str = Field(..., description="Full name of the visitor")
    relationship_with_resident: Relation = Field(
        ...,
        description="Relation: family, spouse, friend, delivery, taxi, etc",
    )
    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    security_id: UUID4 = Field(
        ...,
        description="Security personnel who validated the visit",
    )
    visit_time: datetime = Field(
        ..., description="Timestamp of visitor validation"
    )

    model_config = model_config


class CreateRequest(VisitorLogBase):
    """
    Base request model to CREATE a record.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        user_id (UUID): Reference to the visited resident.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, spouse,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a record.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for visitor log entry"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(VisitorLogBase):
    """
    Base request model to UPDATE a record. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        user_id (UUID): Reference to the visited resident.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, spouse,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        deleted_at: UTC Time when the item was deleted.
    """

    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, VisitorLogBase):
    """
    Base response model to GET a record by id.

    id (UUID): Unique identifier for visitor log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        user_id (UUID): Reference to the visited resident.
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, spouse,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """


class SearchRequest(BaseSearchRequest):
    """
    Request model to GET a list of items that are not archived and filtered
    according to the provided contraints. Items are returned in a chronological
    order based on the creation timestamp.

    Attributes:
        from_date: Filter by creation date (from)
        to_date: Filter by creation date (to)
        page: Page number for pagination
        limit: Number of items per page
        visitor_fullname (str): Full name of the visitor.
        relationship_with_resident (Relationship): Relation: family, spouse,
            friend, delivery, taxi, technician
        hashed_code (str): Visitor's generated access code.
        security_id (UUID): Security personnel who validated the visit
        visit_time (DateTime): Timestamp of visitor validation
    """

    visitor_fullname: str = Field(..., description="Name of the workflow")
    relationship_with_resident: str | None = Field(
        default=None, description="Description of the workflow"
    )
    hashed_code: str = Field(
        ..., description="Version of the workflow in the format 'vX.Y.Z'"
    )
    security_id: str | None = Field(
        default=None,
        description="Unique URL to access and share the results of a "
        "workflow execution",
    )
    visit_time: datetime | None = Field(
        default=None, description="Time when the workflow was deployed"
    )


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of items that are not archived
        page: Current page number
        limit: Number of items per page
        items: Ordered list of table objects
    """

    items: List[GetResponse] = Field(
        ..., description="Ordered list of table objects"
    )
