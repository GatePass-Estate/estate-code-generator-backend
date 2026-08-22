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
    "LimitType",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class LimitType(str, Enum):
    """Enumeration for LimitType."""

    BOOLEAN = "boolean"
    INT = "int"
    COUNT = "count"
    DURATION_DAYS = "duration_days"


class ServiceCatalogBase(BaseModel):
    """Base fields for the resource."""

    service_key: str = Field(..., description="Unique service key")
    name: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Optional description")
    limit_type: LimitType = Field(
        ..., description="boolean|int|count|duration_days"
    )
    is_active: bool = Field(
        default=True, description="Whether catalog entry is active"
    )

    model_config = model_config


class CreateRequest(ServiceCatalogBase):
    """Request model to CREATE a record."""


class CreateResponse(BaseModel):
    """Response model to CREATE a record."""

    id: UUID4 = Field(..., description="Unique identifier")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """Request model to UPDATE a record. All fields optional."""

    service_key: str | None = Field(
        default=None, description="Unique service key"
    )
    name: str | None = Field(default=None, description="Display name")
    description: str | None = Field(
        default=None, description="Optional description"
    )
    limit_type: LimitType | None = Field(
        default=None, description="boolean|int|count|duration_days"
    )
    is_active: bool | None = Field(
        default=None, description="Whether catalog entry is active"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """Response model to UPDATE a record."""

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """Response model to DELETE a record."""

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, ServiceCatalogBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    service_key: Optional[str] = Field(None, description="Unique service key")
    name: Optional[str] = Field(None, description="Display name")
    limit_type: Optional[LimitType] = Field(
        None, description="boolean|int|count|duration_days"
    )
    is_active: Optional[bool] = Field(
        None, description="Whether catalog entry is active"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
