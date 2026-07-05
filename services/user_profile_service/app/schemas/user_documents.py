"""Pydantic schemas for user document API responses."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

model_config = ConfigDict(from_attributes=True, extra="ignore")

__all__ = [
    "DocumentType",
    "DocumentMetadataItem",
    "UserDocumentsMetadataResponse",
    "UploadDocumentResponse",
]


class DocumentType(StrEnum):
    """Supported user document types exposed to clients."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


class DocumentMetadataItem(BaseModel):
    """Metadata and client-facing URLs for one user document."""

    document_type: DocumentType
    content_type: str
    view_url: str
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
    view_url: str
    model_config = model_config
