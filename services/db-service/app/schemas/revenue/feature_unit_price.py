from datetime import datetime
from enum import Enum
from typing import List, Optional
from decimal import Decimal

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "FeatureKind",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class FeatureKind(str, Enum):
    """Enumeration for FeatureKind."""

    SERVICE = "service"
    AI = "ai"


class FeatureUnitPriceBase(BaseModel):
    """Base fields for the resource."""

    country_code: str = Field(..., description="ISO country code")
    currency_code: str = Field(..., description="ISO currency code")
    feature_kind: FeatureKind = Field(..., description="service|ai")
    service_catalog_id: UUID4 | None = Field(
        None, description="FK service_catalog"
    )
    ai_feature_id: UUID4 | None = Field(None, description="FK ai_feature")
    feature_unit_price: Decimal = Field(..., description="Unit price amount")
    is_active: bool = Field(
        default=True, description="Whether price row is active"
    )

    @field_serializer("service_catalog_id")
    def serialize_service_catalog_id(self, value):
        return str(value) if value else None

    @field_serializer("ai_feature_id")
    def serialize_ai_feature_id(self, value):
        return str(value) if value else None

    model_config = model_config


class CreateRequest(FeatureUnitPriceBase):
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

    country_code: str | None = Field(
        default=None, description="ISO country code"
    )
    currency_code: str | None = Field(
        default=None, description="ISO currency code"
    )
    feature_kind: FeatureKind | None = Field(
        default=None, description="service|ai"
    )
    service_catalog_id: UUID4 | None = Field(
        default=None, description="FK service_catalog"
    )
    ai_feature_id: UUID4 | None = Field(
        default=None, description="FK ai_feature"
    )
    feature_unit_price: Decimal | None = Field(
        default=None, description="Unit price amount"
    )
    is_active: bool | None = Field(
        default=None, description="Whether price row is active"
    )

    @field_serializer("service_catalog_id")
    def serialize_service_catalog_id(self, value):
        return str(value) if value else None

    @field_serializer("ai_feature_id")
    def serialize_ai_feature_id(self, value):
        return str(value) if value else None

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


class GetResponse(SharedModel, FeatureUnitPriceBase):
    """Response model to GET a record by id."""


class SearchRequest(BaseSearchRequest):
    """Search/filter request."""

    country_code: Optional[str] = Field(None, description="ISO country code")
    currency_code: Optional[str] = Field(None, description="ISO currency code")
    feature_kind: Optional[FeatureKind] = Field(None, description="service|ai")
    service_catalog_id: UUID4 | None = Field(
        None, description="FK service_catalog"
    )
    ai_feature_id: UUID4 | None = Field(None, description="FK ai_feature")
    is_active: Optional[bool] = Field(
        None, description="Whether price row is active"
    )


class ListResponse(BaseListResponse):
    """Paginated list response."""

    items: List[GetResponse] = Field(..., description="List of records")
