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
    "EstateType",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class EstateType(str, Enum):
    HOUSING = "housing"
    CORPORATE = "corporate"


class EstateBase(BaseModel):
    """
    Base estate model containing common fields.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    lga: str | None = Field(default=None, description="Local Government Area")
    state: str | None = Field(default=None, description="State")
    country: str | None = Field(default=None, description="Country")
    postal_code: str | None = Field(default=None, description="Postal code")
    primary_admin_id: UUID4 | None = Field(
        default=None, description="Reference to the primary admin (optional)"
    )
    estate_type: EstateType | None = Field(
        default=None, description="Type of estate"
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
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
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
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    name: str | None = Field(default=None, description="Estate name")
    location: str | None = Field(default=None, description="Estate location")
    lga: str | None = Field(default=None, description="Local Government Area")
    state: str | None = Field(default=None, description="State")
    country: str | None = Field(default=None, description="Country")
    postal_code: str | None = Field(default=None, description="Postal code")
    primary_admin_id: UUID4 | None = Field(
        default=None, description="Reference to the primary admin"
    )
    estate_type: EstateType | None = Field(
        default=None, description="Type of estate"
    )

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(self, value: UUID4 | None) -> str:
        return str(value) if value else None

    is_active: bool | None = Field(
        default=None, description="Whether the estate is active"
    )
    deactivated_by: UUID4 | None = Field(
        default=None,
        description="ID of the root user who deactivated this estate",
    )

    @field_serializer("deactivated_by")
    def serialize_deactivated_by(self, value: UUID4 | None) -> Optional[str]:
        return str(value) if value else None

    deactivated_at: datetime | None = Field(
        default=None,
        description="When the estate was deactivated",
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


class GetResponse(SharedModel, EstateBase):
    """
    Base response model to GET a record by id.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID): Reference to the primary admin.
        is_active (bool): Whether the estate is active.
        deactivated_by (UUID): Who deactivated the estate.
        deactivated_at (datetime): When the estate was deactivated.
    """

    is_active: bool = Field(
        default=True, description="Whether the estate is active"
    )
    deactivated_by: UUID4 | None = Field(
        default=None,
        description="ID of the root user who deactivated this estate",
    )
    deactivated_at: datetime | None = Field(
        default=None,
        description="When the estate was deactivated",
    )


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
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID): Reference to the primary admin.
    """

    search_query: Optional[str] = Field(
        None, description="Search across name and location"
    )
    name: Optional[str] = Field(None, description="Estate name")
    location: Optional[str] = Field(None, description="Estate location")
    lga: Optional[str] = Field(None, description="Local Government Area")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    postal_code: Optional[str] = Field(None, description="Postal code")
    primary_admin_id: Optional[UUID4] = Field(
        None, description="Reference to the primary admin"
    )
    estate_type: Optional[EstateType] = Field(
        None, description="Type of estate"
    )
    is_active: Optional[bool] = Field(
        None, description="Filter by active/inactive status"
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
