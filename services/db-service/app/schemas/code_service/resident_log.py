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


class ResidentLogBase(BaseModel):
    """
    Base model for resident log table.

    Attributes:
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        full_name (str): Full name of the resident.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access.
        access_time (DateTime): Timestamp of resident access validation.
    """

    user_id: UUID4 = Field(..., description="Reference to the resident")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 = Field(..., description="Reference to the estate")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    full_name: str = Field(..., description="Full name of the resident")
    hashed_code: str = Field(
        ..., description="Resident's generated access code"
    )
    security_id: UUID4 = Field(
        ...,
        description="Security personnel who validated the access",
    )

    @field_serializer("security_id")
    def serialize_security_id(self, value: UUID4) -> str:
        return str(value)

    access_time: datetime = Field(
        ..., description="Timestamp of resident access validation"
    )

    model_config = model_config


class CreateRequest(ResidentLogBase):
    """
    Request model to CREATE a record.

    Attributes:
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        full_name (str): Full name of the resident.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access.
        access_time (DateTime): Timestamp of resident access validation.
    """


class CreateResponse(BaseModel):
    """
    Response model to CREATE a record.

    Attributes:
        id (UUID): Unique identifier for resident log entry.
        created_at (DateTime): Time when the model was created.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for resident log entry"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """
    Request model to UPDATE a record. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        full_name (str): Full name of the resident.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access.
        access_time (DateTime): Timestamp of resident access validation.
    """

    user_id: UUID4 | None = Field(
        default=None, description="Reference to the resident"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 | None = Field(
        default=None, description="Reference to the estate"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    full_name: str | None = Field(
        default=None, description="Full name of the resident"
    )
    hashed_code: str | None = Field(
        default=None, description="Resident's generated access code"
    )
    security_id: UUID4 | None = Field(
        default=None,
        description="Security personnel who validated the access",
    )

    @field_serializer("security_id")
    def serialize_security_id(self, value: UUID4) -> str:
        return str(value)

    access_time: datetime | None = Field(
        default=None, description="Timestamp of resident access validation"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for resident log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Response model to DELETE a record by id.

    Attributes:
        is_deleted: Flag to indicate if the item is (soft) deleted.
        deleted_at: UTC Time when the item was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag to indicate if the record is deleted"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, ResidentLogBase):
    """
    Response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for resident log entry.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        user_id (UUID): Reference to the resident.
        estate_id (UUID): Reference to the estate.
        full_name (str): Full name of the resident.
        hashed_code (str): Resident's generated access code.
        security_id (UUID): Security personnel who validated the access.
        access_time (DateTime): Timestamp of resident access validation.
        usage_count (int): Number of validations for this code; set on unique
            search results only.
        code_deleted (bool): Whether the linked access-code row is
            soft-deleted; set on unique search results only.
    """

    usage_count: int | None = Field(
        default=None,
        description="Total validations for this hashed_code (unique search)",
    )
    code_deleted: bool | None = Field(
        default=None,
        description=(
            "Whether the resident access code is soft-deleted (unique search)"
        ),
    )


class SearchRequest(BaseSearchRequest):
    """
    Request model to search resident log items. Items are returned in
    chronological order based on the creation timestamp.

    Attributes:
        from_date: Filter by creation date (from)
        to_date: Filter by creation date (to)
        page: Page number for pagination
        limit: Number of items per page
        user_id: Reference to the resident.
        estate_id: Reference to the estate.
        full_name: Full name of the resident.
        hashed_code: Resident's generated access code.
        security_id: Security personnel who validated the access.
        access_time: Timestamp of resident access validation.
    """

    user_id: UUID4 | None = Field(
        default=None, description="Reference to the resident"
    )
    estate_id: UUID4 | None = Field(
        default=None, description="Reference to the estate"
    )
    full_name: str | None = Field(
        default=None, description="Full name of the resident"
    )
    hashed_code: str | None = Field(
        default=None, description="Resident's generated access code"
    )
    security_id: UUID4 | None = Field(
        default=None,
        description="Security personnel who validated the access",
    )
    access_time: datetime | None = Field(
        default=None, description="Timestamp of resident access validation"
    )


class ListResponse(BaseListResponse):
    """
    Paginated resident-log search results.

    Consumed by the code-service BFF. Sort direction is controlled by the
    ``ascending`` query parameter on ``/search`` (default: latest first).
    Each item includes denormalized ``full_name``.
    """

    items: List[GetResponse] = Field(
        ..., description="Ordered list of table objects"
    )
