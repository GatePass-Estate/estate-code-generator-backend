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
    "DocumentStatus",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
    "UploadResponse",
    "ApproveResponse",
    "DeleteAllForUserResponse",
]


class DocumentType(StrEnum):
    """Supported user document types stored in GCS."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


class DocumentStatus(StrEnum):
    """Lifecycle status for profile_picture and id_card documents."""

    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


_DOCUMENT_STATUS_TYPES = frozenset(
    {DocumentType.PROFILE_PICTURE, DocumentType.ID_CARD}
)


def default_document_status(
    document_type: DocumentType,
) -> DocumentStatus | None:
    """Return the default status for types that use the status column."""
    if document_type in _DOCUMENT_STATUS_TYPES:
        return DocumentStatus.ACTIVE
    return None


class UserDocumentBase(BaseModel):
    """Shared metadata fields for a user document record."""

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
    document_status: DocumentStatus | None = Field(
        default=None,
        description="Lifecycle status (profile_picture and id_card only)",
    )

    @field_serializer("user_id", "estate_id", "uploaded_by")
    def serialize_uuids(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class CreateRequest(UserDocumentBase):
    """Request model to create a user document metadata record."""


class CreateResponse(BaseModel):
    """Response model after creating a user document metadata row."""

    id: UUID4 = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class UpdateRequest(BaseModel):
    """Partial update payload for user document metadata."""

    gcs_object_path: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    original_filename: str | None = None
    document_status: DocumentStatus | None = None

    model_config = model_config


class UpdateResponse(CreateResponse):
    """Response model after updating a user document metadata row."""

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """Soft-delete confirmation for a user document row."""

    is_deleted: bool = Field(default=True)
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, UserDocumentBase):
    """Full user document metadata record."""


class SearchRequest(BaseSearchRequest):
    """Search filters for listing user document metadata."""

    user_id: UUID4 | None = None
    estate_id: UUID4 | None = None
    document_type: DocumentType | None = None
    uploaded_by: UUID4 | None = None
    document_status: DocumentStatus | None = None


class ListResponse(BaseListResponse):
    """Paginated list of user document metadata records."""

    items: List[GetResponse] = Field(
        ..., description="List of user document records"
    )


class UploadResponse(BaseModel):
    """Response returned after a successful multipart upload."""

    document_type: DocumentType
    content_type: str
    file_size_bytes: int
    gcs_object_path: str
    id: UUID4
    document_status: DocumentStatus | None = None

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class ApproveResponse(BaseModel):
    """Response returned after promoting a pending document to active."""

    id: UUID4
    document_type: DocumentType
    document_status: DocumentStatus
    gcs_object_path: str
    archived_document_id: UUID4 | None = None

    @field_serializer("id", "archived_document_id")
    def serialize_ids(self, value: UUID4 | None) -> str | None:
        if value is None:
            return None
        return str(value)

    model_config = model_config


class DeleteAllForUserResponse(BaseModel):
    """Summary of account-closure document cleanup for one user."""

    deleted_count: int = Field(
        ..., description="Number of document rows soft-deleted"
    )
    gcs_objects_deleted: int = Field(
        ..., description="Number of GCS objects deleted"
    )
    model_config = model_config
