from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import (
    BaseModel,
    Field,
    UUID4,
    ConfigDict,
    field_serializer,
)

__all__ = [
    "EstateType",
    "RegisterEstateRequest",
    "RegisterEstateResponse",
    "UpdateEstateRequest",
    "UpdateEstateResponse",
    "GetEstateResponse",
    "DeleteEstateResponse",
    "SearchEstateRequest",
    "ListEstateResponse",
    "PublicEstateSearchResponse",
    "PublicEstateListResponse",
]


class EstateType(str, Enum):
    HOUSING = "housing"
    CORPORATE = "corporate"


model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class RegisterEstateRequest(BaseModel):
    """
    Base request model to register an estate.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID4): Optional Primary admin ID.
    """

    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    lga: Optional[str] = Field(None, description="Local Government Area")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    postal_code: Optional[str] = Field(None, description="Postal code")
    primary_admin_id: Optional[UUID4] = Field(
        None, description="Primary admin ID"
    )
    estate_type: Optional[EstateType] = Field(
        None, description="Type of estate"
    )

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(
        self, primary_admin_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(primary_admin_id) if primary_admin_id else None

    model_config = model_config


class RegisterEstateResponse(BaseModel):
    """
    Response model for estate registration.

    Attributes:
        id (UUID4): Estate ID.
        name (str): Estate name.
        location (str): Estate location.
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID4): Primary admin ID.
        created_at (datetime): Creation timestamp.
    """

    id: UUID4 = Field(..., description="Estate ID")
    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    lga: Optional[str] = Field(None, description="Local Government Area")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    postal_code: Optional[str] = Field(None, description="Postal code")
    primary_admin_id: Optional[UUID4] = Field(
        None, description="Primary admin ID"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(
        self, primary_admin_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(primary_admin_id) if primary_admin_id else None

    model_config = model_config


class UpdateEstateRequest(BaseModel):
    """
    Request model to update an estate. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        name (str): Estate name.
        location (str): Estate location.
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID4): Reference to the primary admin.
    """

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

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(
        self, primary_admin_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(primary_admin_id) if primary_admin_id else None

    model_config = model_config


class UpdateEstateResponse(BaseModel):
    """
    Response model for estate update operations.

    Attributes:
        id (UUID4): Estate ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """

    id: UUID4 = Field(..., description="Estate ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class GetEstateResponse(BaseModel):
    """
    Response model to get an estate by ID.

    Attributes:
        id (UUID4): Estate ID.
        name (str): Estate name.
        location (str): Estate location.
        lga (str): Local Government Area.
        state (str): State.
        country (str): Country.
        postal_code (str): Postal code.
        primary_admin_id (UUID4): Primary admin ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        is_deleted (bool): Deletion status.
    """

    id: UUID4 = Field(..., description="Estate ID")
    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    lga: Optional[str] = Field(None, description="Local Government Area")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    postal_code: Optional[str] = Field(None, description="Postal code")
    primary_admin_id: Optional[UUID4] = Field(
        None, description="Primary admin ID"
    )
    estate_type: Optional[EstateType] = Field(
        None, description="Type of estate"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(
        None, description="Last update timestamp"
    )
    is_deleted: bool = Field(False, description="Deletion status")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(
        self, primary_admin_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(primary_admin_id) if primary_admin_id else None

    model_config = model_config


class DeleteEstateResponse(BaseModel):
    """
    Response model for estate deletion (soft delete).

    Attributes:
        is_deleted (bool): Whether the estate was deleted (soft delete).
        deleted_at (datetime): UTC Time when the estate was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config


class SearchEstateRequest(BaseModel):
    """
    Request model to search estates with optional filters and pagination.

    Attributes:
        name (str): Filter by estate name (partial match).
        location (str): Filter by estate location (partial match).
        lga (str): Filter by LGA (partial match).
        state (str): Filter by state (partial match).
        country (str): Filter by country (partial match).
        postal_code (str): Filter by postal code (partial match).
        primary_admin_id (UUID4): Filter by primary admin ID.
        from_date (datetime): Filter by creation date (from).
        to_date (datetime): Filter by creation date (to).
        page (int): Page number for pagination.
        limit (int): Number of items per page.
    """

    search_query: Optional[str] = Field(
        None, description="Search across estate name and location"
    )
    name: Optional[str] = Field(None, description="Filter by estate name")
    location: Optional[str] = Field(
        None, description="Filter by estate location"
    )
    lga: Optional[str] = Field(None, description="Filter by LGA")
    state: Optional[str] = Field(None, description="Filter by state")
    country: Optional[str] = Field(None, description="Filter by country")
    postal_code: Optional[str] = Field(
        None, description="Filter by postal code"
    )
    primary_admin_id: Optional[UUID4] = Field(
        None, description="Filter by primary admin ID"
    )
    estate_type: Optional[EstateType] = Field(
        None, description="Filter by estate type"
    )
    from_date: Optional[datetime] = Field(
        None, description="Filter by creation date (from)"
    )
    to_date: Optional[datetime] = Field(
        None, description="Filter by creation date (to)"
    )
    page: int = Field(1, ge=1, description="Page number for pagination")
    limit: int = Field(
        10, ge=1, le=100, description="Number of items per page"
    )

    @field_serializer("primary_admin_id")
    def serialize_primary_admin_id(
        self, primary_admin_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(primary_admin_id) if primary_admin_id else None

    model_config = model_config


class ListEstateResponse(BaseModel):
    """
    Response model for estate list/search operations.

    Attributes:
        total (int): Total number of estates matching the search criteria.
        page (int): Current page number.
        limit (int): Number of items per page.
        items (List[GetEstateResponse]): List of estate records.
    """

    total: int = Field(..., description="Total number of estates")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[GetEstateResponse] = Field(
        ..., description="List of estate records"
    )

    model_config = model_config


class PublicEstateSearchResponse(BaseModel):
    """
    Public estate record returned in unauthenticated search results.

    Attributes:
        id (UUID4): Estate ID.
        name (str): Estate name.
        location (str): Estate location.
        estate_type (EstateType): Type of estate.
    """

    id: UUID4 = Field(..., description="Estate ID")
    name: str = Field(..., description="Estate name")
    location: str = Field(..., description="Estate location")
    estate_type: Optional[EstateType] = Field(
        None, description="Type of estate"
    )

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class PublicEstateListResponse(BaseModel):
    """
    Response model for public estate search.

    Attributes:
        total (int): Total number of matching estates.
        page (int): Current page number.
        limit (int): Number of items per page.
        items (List[PublicEstateSearchResponse]): List of public estate
            records.
    """

    total: int = Field(..., description="Total number of estates")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[PublicEstateSearchResponse] = Field(
        ..., description="List of public estate records"
    )

    model_config = model_config
