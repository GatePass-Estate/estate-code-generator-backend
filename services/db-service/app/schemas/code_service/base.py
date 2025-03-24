from datetime import datetime, timezone
from enum import Enum

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)


class GCPSignedUrlConfig(BaseModel):
    """Configuration for GCP signed URL generation."""

    service_account_file: str | None = Field(
        None, description="Path to the GCP service account credentials file"
    )


class Access(str, Enum):
    """
    Enumeration of supported access levels.
    """

    PUBLIC = "public"  # Entity open to be used in the UI
    SYSTEM = "system"  # Entity for system use only
    INTERNAL = "internal"  # Entity for QH internal use


class Status(str, Enum):
    """
    Enumeration of availability status of a record.
    """

    AVAILABLE = "available"  # Entity is available to use
    ARCHIVED = "archived"  # Entity is archived
    DELETED = "deleted"  # Entity is deleted


# Shared configuration for the pydantic models
model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class SharedModel(BaseModel):
    """
    Base Workflow Model used by all the tables under workflow schema.

    Attributes:
        id: Unique identifier of the record
        access: Access level of the record
        status: Availability status of the record
        created_at: Creation timestamp
        updated_at: Last updated timestamp
        is_deleted: Flag to indicate if the record is deleted
    """

    id: UUID4 = Field(..., description="Unique identifier of the record")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    access: Access | None = Field(
        default=None, description="Access level of the record"
    )
    status: Status | None = Field(
        default=None, description="Status of the record"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    is_deleted: bool | None = Field(
        default=False, description="Flag to indicate if the record is deleted"
    )
    model_config = model_config


class BaseSearchRequest(BaseModel):
    """
    Base request model to GET a list of items that are not archived and filtered
    according to the provided contraints. Items are returned in a chronological
    order based on the creation timestamp.

    Attributes:
        access: Access level of the record
        status: Availability status of the record
        from_date: Filter by creation date (from)
        to_date: Filter by creation date (to)
        page: Page number for pagination
        limit: Number of items per page
    """

    access: Access | str | None = Field(
        None, description="Access level of the record"
    )
    status: Status | str | None = Field(
        None, description="Status of the record"
    )
    from_date: datetime | None = Field(
        None,
        description="Filters records with creation date 'from' YYYY-MM-DD."
        " Defaults to None",
    )
    to_date: datetime | None = Field(
        None,
        description="Filters records with creation date up 'to' YYYY-MM-DD."
        " Defaults to None",
    )
    page: int = Field(1, ge=1, description="Page number for pagination")
    limit: int = Field(
        10, ge=1, le=100, description="Number of items per page"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_inputs(cls, data):
        # data transformations
        data["from_date"] = (
            datetime.combine(
                data["from_date"], datetime.min.time(), tzinfo=timezone.utc
            )
            if data["from_date"] is not None
            else None
        )  # Convert date to datetime from start of the day
        data["to_date"] = (
            datetime.combine(
                data["to_date"], datetime.max.time(), tzinfo=timezone.utc
            )
            if data["to_date"] is not None
            else None
        )  # Convert date to datetime from start of the day

        return data

    model_config = model_config


class BaseListResponse(BaseModel):
    """
    Base response model to GET the list of all items that are not archived.
    Items are returned in a chronological order based on the creation timestamp

    Attributes:
        total: Total number of items that are not archived
        page: Current page number
        limit: Number of items per page
    """

    total: int = Field(..., description="Total number of items")
    page: int | None = Field(1, description="Current page number")
    limit: int | None = Field(20, description="Number of items per page")
    model_config = model_config
