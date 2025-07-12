from datetime import datetime
from typing import List, Optional

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
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


class ResidentDepartureLogBase(BaseModel):
    """
    Base resident model containing common fields.

    Attributes:
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        admin_id (UUID): Admin who approved the departure.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
    """

    user_id: UUID4 = Field(..., description="Resident who left")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 = Field(..., description="Related estate")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    admin_id: UUID4 | None = Field(
        None, description="Admin who approved the departure"
    )

    @field_serializer("admin_id")
    def serialize_admin_id(self, value: UUID4) -> str:
        return str(value)

    departure_time: datetime = Field(..., description="Timestamp of exit")
    reason: str = Field(..., description="Optional reason for leaving")

    model_config = model_config


class CreateRequest(ResidentDepartureLogBase):
    """
    Base request model to CREATE a resident departure log record.

    Attributes:
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        admin_id (UUID): Admin who approved the departure.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created resident departure log.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ...,
        description="Unique identifier for the created resident departure log",
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
        id (UUID): Unique identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        admin_id (UUID): Admin who approved the departure.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
    """

    user_id: UUID4 | None = Field(
        default=None, description="Resident who left"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 | None = Field(default=None, description="Related estate")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    admin_id: UUID4 | None = Field(
        default=None, description="Admin who approved the departure"
    )

    @field_serializer("admin_id")
    def serialize_admin_id(self, value: UUID4) -> str:
        return str(value)

    departure_time: datetime | None = Field(
        default=None, description="Timestamp of exit"
    )
    reason: str | None = Field(
        default=None, description="Optional reason for leaving"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for the updated user.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Whether the user was deleted (soft delete).
        deleted_at: UTC Time when the user was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, ResidentDepartureLogBase):
    """
    Base response model to GET a record by id.

    Attributes:
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
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
        user_id (UUID): Resident who left.
        estate_id (UUID): Related estate.
        admin_id (UUID): Admin who approved the departure.
        departure_time (DateTime): Timestamp of exit.
        reason (Text): Optional reason for leaving.
    """

    user_id: Optional[UUID4] = Field(None, description="Resident who left")
    estate_id: Optional[UUID4] = Field(None, description="Related estate")
    admin_id: Optional[UUID4] = Field(
        None, description="Admin who approved the departure"
    )
    departure_time: Optional[datetime] = Field(
        None, description="Timestamp of exit"
    )
    reason: Optional[str] = Field(
        None, description="Optional reason for leaving"
    )


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of users.
        page: Current page number.
        limit: Number of items per page.
        items: List of user records.
    """

    items: List[GetResponse] = Field(
        ..., description="List of resident departure log records"
    )
