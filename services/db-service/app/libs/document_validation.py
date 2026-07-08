"""Validation helpers for user document uploads."""

from __future__ import annotations

from gatepass_docs import (
    extension_for_content_type,
    validate_content_type as shared_validate_content_type,
    validate_magic_bytes,
)

from app.core.exceptions import DocumentValidationError
from app.core.config import settings
from app.schemas.user_profile.user_documents import DocumentType

__all__ = [
    "DocumentType",
    "DocumentValidationError",
    "build_object_path",
    "max_bytes_for_type",
    "validate_content_type",
    "validate_file_size",
    "validate_magic_bytes",
]


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


def build_object_path(
    *,
    estate_id: str,
    user_id: str,
    document_type: DocumentType,
    document_id: str,
    content_type: str,
    pending: bool = False,
) -> str:
    """Build the GCS object key for a new upload (main or temp folder)."""
    extension = extension_for_content_type(content_type)
    prefix = (
        f"estates/{estate_id}/users/{user_id}/temp/"
        if pending
        else f"estates/{estate_id}/users/{user_id}/"
    )
    return f"{prefix}{document_type.value}_{document_id}.{extension}"
