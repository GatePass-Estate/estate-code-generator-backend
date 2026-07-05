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
    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


class DocumentMetadataItem(BaseModel):
    document_type: DocumentType
    content_type: str
    view_url: str
    download_url: str | None = Field(
        default=None,
        description="Present only when the requester may download this document",
    )
    model_config = model_config


class UserDocumentsMetadataResponse(BaseModel):
    documents: list[DocumentMetadataItem]
    model_config = model_config


class UploadDocumentResponse(BaseModel):
    document_type: DocumentType
    content_type: str
    file_size_bytes: int
    view_url: str
    model_config = model_config
