from datetime import datetime
from enum import StrEnum
from typing import List

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "DocumentType",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
    "UploadResponse",
    "DeleteAllForUserResponse",
]


class DocumentType(StrEnum):
    """Supported user document types stored in GCS."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


class UserDocumentBase(BaseModel):
    user_id: UUID4 = Field(..., description="Document owner user ID")
    estate_id: UUID4 = Field(..., description="Estate ID (denormalized)")
    document_type: DocumentType = Field(..., description="Document type")
    gcs_object_path: str = Field(..., description="Stable GCS object path")
    content_type: str = Field(..., description="MIME type")
    file_size_bytes: int | None = Field(
        default=None, description="File size in bytes"
    )
    original_filename: str | None = Field(
        default=None, description="Original upload filename"
    )
    uploaded_by: UUID4 = Field(..., description="Uploader user ID")

    @field_serializer("user_id", "estate_id", "uploaded_by")
    def serialize_uuids(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class CreateRequest(UserDocumentBase):
    """Request model to create a user document metadata record."""


class CreateResponse(BaseModel):
    id: UUID4 = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class UpdateRequest(BaseModel):
    gcs_object_path: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    original_filename: str | None = None

    model_config = model_config


class UpdateResponse(CreateResponse):
    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    is_deleted: bool = Field(default=True)
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, UserDocumentBase):
    """Full user document metadata record."""


class SearchRequest(BaseSearchRequest):
    user_id: UUID4 | None = None
    estate_id: UUID4 | None = None
    document_type: DocumentType | None = None
    uploaded_by: UUID4 | None = None


class ListResponse(BaseListResponse):
    items: List[GetResponse] = Field(
        ..., description="List of user document records"
    )


class UploadResponse(BaseModel):
    document_type: DocumentType
    content_type: str
    file_size_bytes: int
    gcs_object_path: str
    id: UUID4

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class DeleteAllForUserResponse(BaseModel):
    deleted_count: int = Field(
        ..., description="Number of document rows soft-deleted"
    )
    gcs_objects_deleted: int = Field(
        ..., description="Number of GCS objects deleted"
    )
    model_config = model_config
