"""Validation helpers for user document uploads (UPS layer)."""

from __future__ import annotations

from enum import StrEnum

_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF"

PROFILE_PICTURE_MAX_BYTES = 5 * 1024 * 1024
ID_CARD_MAX_BYTES = 10 * 1024 * 1024


class DocumentType(StrEnum):
    """Supported user document types."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


_ALLOWED_CONTENT_TYPES: dict[DocumentType, set[str]] = {
    DocumentType.PROFILE_PICTURE: {"image/jpeg"},
    DocumentType.ID_CARD: {"image/jpeg", "application/pdf"},
}


class DocumentValidationError(ValueError):
    """Raised when an uploaded document fails validation."""


def max_bytes_for_type(document_type: DocumentType) -> int:
    """Return the configured upload size limit for a document type."""
    if document_type == DocumentType.PROFILE_PICTURE:
        return PROFILE_PICTURE_MAX_BYTES
    return ID_CARD_MAX_BYTES


def validate_content_type(
    document_type: DocumentType, content_type: str | None
) -> str:
    """Validate and return the MIME type allowed for the document type."""
    if not content_type:
        raise DocumentValidationError("Content type is required")
    allowed = _ALLOWED_CONTENT_TYPES[document_type]
    if content_type not in allowed:
        raise DocumentValidationError(
            f"Unsupported content type '{content_type}' for {document_type}"
        )
    return content_type


def validate_file_size(document_type: DocumentType, size: int) -> None:
    """Raise DocumentValidationError when the file is empty or oversize."""
    max_bytes = max_bytes_for_type(document_type)
    if size <= 0:
        raise DocumentValidationError("File is empty")
    if size > max_bytes:
        raise DocumentValidationError(
            f"File exceeds maximum size of {max_bytes} bytes"
        )


def validate_magic_bytes(content_type: str, data: bytes) -> None:
    """Raise DocumentValidationError when file magic bytes do not match MIME."""
    if content_type == "image/jpeg" and not data.startswith(_JPEG_MAGIC):
        raise DocumentValidationError("File is not a valid JPEG image")
    if content_type == "application/pdf" and not data.startswith(_PDF_MAGIC):
        raise DocumentValidationError("File is not a valid PDF document")
