"""Validation helpers for user document uploads (UPS layer)."""

from __future__ import annotations

from enum import StrEnum

from app.core.config import settings
from gatepass_docs import (  # pyright: ignore[reportMissingImports]
    DocumentValidationError,
    validate_content_type as shared_validate_content_type,
    validate_magic_bytes,
)

__all__ = [
    "DocumentType",
    "DocumentValidationError",
    "max_bytes_for_type",
    "validate_content_type",
    "validate_file_size",
    "validate_magic_bytes",
]


class DocumentType(StrEnum):
    """Supported user document types."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"


def max_bytes_for_type(document_type: DocumentType) -> int:
    """Return the configured upload size limit for a document type."""
    if document_type == DocumentType.PROFILE_PICTURE:
        return settings.GCS_PROFILE_PICTURE_MAX_BYTES
    return settings.GCS_ID_CARD_MAX_BYTES


def validate_content_type(
    document_type: DocumentType, content_type: str | None
) -> str:
    """Validate and return the MIME type allowed for the document type."""
    return shared_validate_content_type(document_type, content_type)


def validate_file_size(document_type: DocumentType, size: int) -> None:
    """Raise DocumentValidationError when the file is empty or oversize."""
    max_bytes = max_bytes_for_type(document_type)
    if size <= 0:
        raise DocumentValidationError("File is empty")
    if size > max_bytes:
        raise DocumentValidationError(
            f"File exceeds maximum size of {max_bytes} bytes"
        )
