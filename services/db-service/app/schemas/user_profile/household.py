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


class HouseholdBase(BaseModel):
    """
    Base household model containing common fields.

    Attributes:
        estate_id (UUID): Estate the household is in.
        name (str): Display name of the household.
        head_user_id (UUID): Optional head/lead of the household.
    """

    estate_id: UUID4 = Field(..., description="Estate the household is in")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    name: str = Field(..., description="Display name of the household")

    head_user_id: Optional[UUID4] = Field(
        default=None, description="Head/lead of the household"
    )

    @field_serializer("head_user_id")
    def serialize_head_user_id(self, value: Optional[UUID4]) -> Optional[str]:
        return str(value) if value else None

    model_config = model_config


class CreateRequest(HouseholdBase):
    """
    Request model to CREATE a household record.

    Attributes:
        estate_id (UUID): Estate the household is in.
        name (str): Display name of the household.
        head_user_id (UUID): Optional head/lead of the household.
    """


class CreateResponse(BaseModel):
    """
    Response model after CREATE.

    Attributes:
        id (UUID): Unique identifier for the created household.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created household"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """
    Request model to UPDATE a household record. All fields are optional;
    only supplied fields are updated.

    Attributes:
        name (str): Display name of the household.
        head_user_id (UUID): Head/lead of the household (None clears it).
    """

    name: Optional[str] = Field(
        default=None, description="Display name of the household"
    )
    head_user_id: Optional[UUID4] = Field(
        default=None, description="Head/lead of the household"
    )

    @field_serializer("head_user_id")
    def serialize_head_user_id(self, value: Optional[UUID4]) -> Optional[str]:
        return str(value) if value else None

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Response model after UPDATE.

    Attributes:
        id (UUID): Unique identifier for the updated household.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Response model after DELETE (soft delete).

    Attributes:
        is_deleted: Whether the household was deleted.
        deleted_at: UTC timestamp of deletion.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, HouseholdBase):
    """
    Response model for GET by id.

    Attributes:
        estate_id (UUID): Estate the household is in.
        name (str): Display name of the household.
        head_user_id (UUID): Optional head/lead of the household.
    """


class SearchRequest(BaseSearchRequest):
    """
    Request model to search households with optional filters.

    Attributes:
        from_date: Filter by creation date (from).
        to_date: Filter by creation date (to).
        page: Page number for pagination.
        limit: Number of items per page.
        estate_id (UUID): Filter by estate.
        name (str): Substring match on household name.
        head_user_id (UUID): Filter by head user.
    """

    estate_id: Optional[UUID4] = Field(
        default=None, description="Estate the household is in"
    )
    name: Optional[str] = Field(
        default=None,
        description="Substring match on household name",
    )
    head_user_id: Optional[UUID4] = Field(
        default=None, description="Head/lead of the household"
    )


class ListResponse(BaseListResponse):
    """
    Response model for paginated household lists.

    Attributes:
        total: Total number of households.
        page: Current page number.
        limit: Number of items per page.
        items: List of household records.
    """

    items: List[GetResponse] = Field(
        ..., description="List of household records"
    )
