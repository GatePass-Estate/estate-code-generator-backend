from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "RequestType",
    "Status",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class RequestType(str, Enum):
    """
    Type of Request
    """

    FIRST_NAME_CHANGE = "first_name_change"
    LAST_NAME_CHANGE = "last_name_change"
    HOME_ADDRESS_CHANGE = "home_address_change"
    EMAIL_CHANGE = "email_change"
    GENDER_CHANGE = "gender_change"
    VACATE_RESIDENCE = "vacate_residence"
    ID_CHANGE = "id_change"


class Status(str, Enum):
    """
    Status of Request
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestBase(BaseModel):
    """
    Base request model containing common fields.

    Attributes:
        resident_id (UUID): Resident making the request.
        estate_id (UUID): Estate of the request.
        request_type (RequestType): Type of change.
        old_value (str): Old value.
        new_value (str): New value.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
    """

    resident_id: UUID4 = Field(..., description="Resident making the request")

    estate_id: UUID4 = Field(..., description="Estate of the request")

    request_type: RequestType = Field(..., description="Type of change")

    old_value: str = Field(..., description="Old value")

    new_value: str | None = Field(None, description="New value")

    status: Status = Field(..., description="Status of the request")

    reviewed_by: UUID4 | None = Field(
        None, description="User who reviewed the request"
    )

    @field_serializer("resident_id")
    def serialize_resident_id(self, value: UUID4) -> str:
        return str(value) if value else None

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value) if value else None

    @field_serializer("reviewed_by")
    def serialize_reviewed_by(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class CreateRequest(RequestBase):
    """
    Base request model to CREATE a request record.

    Attributes:
        resident_id (UUID): Resident making the request.
        estate_id (UUID): Estate of the request.
        request_type (RequestType): Type of change.
        old_value (str): Old value.
        new_value (str): New value.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created request.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created request"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """
    Base request model to UPDATE a record. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        id (UUID): Unique identifier for each request.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        resident_id (UUID): Resident making the request.
        estate_id (UUID): Estate of the request.
        request_type (RequestType): Type of change.
        old_value (str): Old value.
        new_value (str): New value.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
    """

    resident_id: UUID4 | None = Field(
        default=None, description="Resident making the request"
    )

    estate_id: UUID4 | None = Field(
        default=None, description="Estate of the request"
    )

    request_type: RequestType | None = Field(
        default=None, description="Type of change"
    )

    old_value: str | None = Field(default=None, description="Old value")

    new_value: str | None = Field(default=None, description="New value")

    status: Status | None = Field(
        default=None, description="Status of the request"
    )

    reviewed_by: UUID4 | None = Field(
        default=None, description="User who reviewed the request"
    )
    last_reminded_at: datetime | None = Field(
        default=None,
        description="When the user last sent a reminder to admins",
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value) if value else None

    @field_serializer("resident_id")
    def serialize_resident_id(self, value: UUID4) -> str:
        return str(value) if value else None

    @field_serializer("reviewed_by")
    def serialize_reviewed_by(self, value: UUID4) -> str:
        return str(value) if value else None

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for the updated request.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")
    status: Status = Field(..., description="Status of the request")
    reviewed_by: UUID4 | None = Field(
        None, description="User who reviewed the request"
    )

    @field_serializer("reviewed_by")
    def serialize_reviewed_by(self, value: UUID4) -> str:
        return str(value) if value else None


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Whether the request was deleted (soft delete).
        deleted_at: UTC Time when the request was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, RequestBase):
    """
    Base response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for each request.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        resident_id (UUID): Resident making the request.
        estate_id (UUID): Estate of the request.
        request_type (RequestType): Type of change.
        old_value (str): Old value.
        new_value (str): New value.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
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
        resident_id (UUID): Resident making the request.
        estate_id (UUID): Estate of the request.
        request_type (RequestType): Type of change.
        old_value (str): Old value.
        new_value (str): New value.
        status (Status): Status of the request.
        reviewed_by (UUID): User who reviewed the request.
    """

    resident_id: Optional[UUID4] = Field(
        default=None, description="Resident making the request"
    )

    estate_id: Optional[UUID4] = Field(
        default=None, description="Estate of the request"
    )

    request_type: Optional[RequestType] = Field(
        default=None, description="Type of change"
    )

    old_value: Optional[str] = Field(default=None, description="Old value")

    new_value: Optional[str] = Field(default=None, description="New value")

    status: Optional[Status] = Field(
        default=None, description="Status of the request"
    )

    reviewed_by: Optional[UUID4] = Field(
        default=None, description="User who reviewed the request"
    )


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of requests.
        page: Current page number.
        limit: Number of items per page.
        items: List of request records.
    """

    items: List[GetResponse] = Field(
        ..., description="List of request records"
    )
