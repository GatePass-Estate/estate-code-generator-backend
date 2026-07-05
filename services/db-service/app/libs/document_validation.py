"""Validation helpers for user document uploads."""

from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import DocumentValidationError
from app.schemas.user_profile.user_documents import DocumentType

_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF"

_ALLOWED_CONTENT_TYPES: dict[DocumentType, set[str]] = {
    DocumentType.PROFILE_PICTURE: {"image/jpeg"},
    DocumentType.ID_CARD: {"image/jpeg", "application/pdf"},
}

_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "application/pdf": "pdf",
}


def max_bytes_for_type(document_type: DocumentType) -> int:
    if document_type == DocumentType.PROFILE_PICTURE:
        return settings.GCS_PROFILE_PICTURE_MAX_BYTES
    return settings.GCS_ID_CARD_MAX_BYTES


def validate_content_type(
    document_type: DocumentType, content_type: str | None
) -> str:
    if not content_type:
        raise DocumentValidationError("Content type is required")
    allowed = _ALLOWED_CONTENT_TYPES[document_type]
    if content_type not in allowed:
        raise DocumentValidationError(
            f"Unsupported content type '{content_type}' for {document_type}"
        )
    return content_type


def validate_file_size(document_type: DocumentType, size: int) -> None:
    max_bytes = max_bytes_for_type(document_type)
    if size <= 0:
        raise DocumentValidationError("File is empty")
    if size > max_bytes:
        raise DocumentValidationError(
            f"File exceeds maximum size of {max_bytes} bytes"
        )


def validate_magic_bytes(content_type: str, data: bytes) -> None:
    if content_type == "image/jpeg" and not data.startswith(_JPEG_MAGIC):
        raise DocumentValidationError("File is not a valid JPEG image")
    if content_type == "application/pdf" and not data.startswith(_PDF_MAGIC):
        raise DocumentValidationError("File is not a valid PDF document")


def build_object_path(
    *,
    estate_id: str,
    user_id: str,
    document_type: DocumentType,
    document_id: str,
    content_type: str,
) -> str:
    extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
    return (
        f"estates/{estate_id}/users/{user_id}/"
        f"{document_type.value}_{document_id}.{extension}"
    )
