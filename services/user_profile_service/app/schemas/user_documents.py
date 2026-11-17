"""Pydantic schemas for user document API responses."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

model_config = ConfigDict(from_attributes=True, extra="ignore")

__all__ = [
    "DocumentType",
    "DocumentStatus",
    "DocumentMetadataItem",
    "UserDocumentsMetadataResponse",
    "UploadDocumentResponse",
]


class DocumentType(StrEnum):
    """Supported user document types exposed to clients."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


class DocumentStatus(StrEnum):
    """Lifecycle status for profile_picture and id_card documents."""

    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentMetadataItem(BaseModel):
    """Metadata and client-facing URLs for one user document."""

    document_type: DocumentType
    content_type: str
    document_status: DocumentStatus | None = None
    document_id: str | None = Field(
        default=None,
        description="Document row ID (present for pending uploads)",
    )
    view_url: str | None = None
    download_url: str | None = Field(
        default=None,
        description="Present only when the requester may download this document",
    )
    model_config = model_config


class UserDocumentsMetadataResponse(BaseModel):
    """List of document metadata entries for a user."""

    documents: list[DocumentMetadataItem]
    model_config = model_config


class UploadDocumentResponse(BaseModel):
    """Response returned after a successful document upload."""

    document_type: DocumentType
    content_type: str
    file_size_bytes: int
    document_id: str
    document_status: DocumentStatus | None = None
    view_url: str | None = Field(
        default=None,
        description="Present only when the document is immediately active",
    )
    edit_request_id: str | None = Field(
        default=None,
        description="Pending edit request ID when an ID card awaits approval",
    )
    model_config = model_config
