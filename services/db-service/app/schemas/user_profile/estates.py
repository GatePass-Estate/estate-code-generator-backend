from datetime import datetime
from typing import List

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


class EstateBase(BaseModel):
    """
    Base estate model containing common fields.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    primary_admin_id: UUID4 | None = Field(
        default=None, description="Reference to the primary admin (optional)"
    )

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(self, value: UUID4 | None) -> str:
        return str(value) if value else None

    model_config = model_config


class CreateRequest(EstateBase):
    """
    Base request model to CREATE an estate record.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        primary_admin_id (UUID | None): Reference to the primary admin.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created estate.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created estate"
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
        id (UUID): Unique estate identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        name (str): Estate name.
        location (str): Estate location.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    name: str | None = Field(default=None, description="Estate name")
    location: str | None = Field(default=None, description="Estate location")
    primary_admin_id: UUID4 | None = Field(
        default=None, description="Reference to the primary admin"
    )

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(self, value: UUID4 | None) -> str:
        return str(value) if value else None

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


class GetResponse(SharedModel, EstateBase):
    """
    Base response model to GET a record by id.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        primary_admin_id (UUID): Reference to the primary admin.
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
        name (str): Estate name.
        location (str): Estate location.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    primary_admin_id: UUID4 = Field(
        ..., description="Reference to the primary admin"
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

    items: List[GetResponse] = Field(..., description="List of estate records")
