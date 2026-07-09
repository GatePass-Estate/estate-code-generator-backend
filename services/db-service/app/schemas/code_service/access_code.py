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


class AccessCodeBase(BaseModel):
    """
    Model for Composer Workflows table.

    Attributes:
        user_id (UUID): Reference to the resident generating code.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Securely stored hash of access code.
        valid_until (DateTime): Expiration timestamp for the access code.
    """

    user_id: UUID4 = Field(
        ..., description="Reference to the visited resident"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 = Field(..., description="Full name of the visitor")

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    hashed_code: str = Field(
        ..., description="Visitor's generated access code"
    )
    valid_until: datetime = Field(
        ..., description="Timestamp of visitor validation"
    )

    model_config = model_config


class CreateRequest(AccessCodeBase):
    """
    Base request model to CREATE a record.

    Attributes:
        user_id (UUID): Reference to the resident generating code.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Securely stored hash of access code.
        valid_until (DateTime): Expiration timestamp for the access code.
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


class UpdateRequest(BaseModel):
    """
    Base request model to UPDATE a record. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        id (UUID): Unique identifier for the access code.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        user_id (UUID): Reference to the resident generating code.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Securely stored hash of access code.
        valid_until (DateTime): Expiration timestamp for the access code.
    """

    user_id: UUID4 | None = Field(
        default=None, description="Reference to the visited resident"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    estate_id: UUID4 | None = Field(
        default=None, description="Full name of the visitor"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, value: UUID4) -> str:
        return str(value)

    hashed_code: str | None = Field(
        default=None, description="Visitor's generated access code"
    )
    valid_until: datetime | None = Field(
        default=None, description="Timestamp of visitor validation"
    )

    model_config = model_config


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

    is_deleted: bool = Field(
        default=True, description="Flag to indicate if the record is deleted"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, AccessCodeBase):
    """
    Base response model to GET a record by id.

    Attributes:
        id (UUID): Unique identifier for the access code.
        created_at (DateTime): Time when the model was created.
        updated_at (DateTime): Time when the model was last updated.
        deleted_at (Optional[DateTime]): UTC Time when the item was deleted.
        user_id (UUID): Reference to the resident generating code.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Securely stored hash of access code.
        valid_until (DateTime): Expiration timestamp for the access code.
    """

    deleted_at: datetime | None = Field(
        default=None, description="UTC timestamp of soft deletion"
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
        user_id (UUID): Reference to the resident generating code.
        estate_id (UUID): Reference to the estate.
        hashed_code (str): Securely stored hash of access code.
        valid_until (DateTime): Expiration timestamp for the access code.
    """

    user_id: UUID4 | None = Field(
        default=None, description="Reference to the visited resident"
    )
    estate_id: UUID4 | None = Field(
        default=None, description="Full name of the visitor"
    )
    hashed_code: str | None = Field(
        default=None,
        description="Version of the workflow in the format 'vX.Y.Z'",
    )
    valid_until: datetime | None = Field(
        default=None, description="Time when the workflow was deployed"
    )


class ListResponse(BaseListResponse):
    """
    Paginated access-code search results.

    Consumed by code-service for resident-code management and for resolving
    the earliest row on code-level resident history (``include_deleted`` and
    ``ascending`` on ``/search``).
    """

    items: List[GetResponse] = Field(
        ..., description="Ordered list of table objects"
    )
