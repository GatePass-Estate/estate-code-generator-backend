"""Shared MIME types, extensions, and magic-byte checks for user documents."""

from __future__ import annotations

from typing import Any

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_PDF_MAGIC = b"%PDF"
_HEIF_BRANDS = frozenset(
    {
        b"heic",
        b"heif",
        b"mif1",
        b"msf1",
        b"heix",
        b"hevc",
        b"heim",
        b"heis",
        b"hevm",
        b"hevs",
    }
)

IMAGE_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
)

ALLOWED_CONTENT_TYPES: dict[str, frozenset[str]] = {
    "profile_picture": IMAGE_CONTENT_TYPES,
    "id_card": IMAGE_CONTENT_TYPES | {"application/pdf"},
}

CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    "application/pdf": "pdf",
}


class DocumentValidationError(ValueError):
    """Raised when an uploaded document fails validation."""


def _document_type_value(document_type: Any) -> str:
    value = getattr(document_type, "value", document_type)
    return str(value)


def allowed_content_types_for(document_type: Any) -> frozenset[str]:
    """Return allowed MIME types for a document type key."""
    key = _document_type_value(document_type)
    try:
        return ALLOWED_CONTENT_TYPES[key]
    except KeyError as exc:
        raise DocumentValidationError(
            f"Unsupported document type: {document_type}"
        ) from exc


def validate_content_type(document_type: Any, content_type: str | None) -> str:
    """Validate and return the MIME type allowed for the document type."""
    if not content_type:
        raise DocumentValidationError("Content type is required")
    normalized = content_type.strip().lower()
    allowed = allowed_content_types_for(document_type)
    if normalized not in allowed:
        raise DocumentValidationError(
            f"Unsupported content type '{content_type}' for {document_type}"
        )
    return normalized


def extension_for_content_type(content_type: str) -> str:
    """Return the file extension for a supported MIME type."""
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)
    if extension is None:
        raise DocumentValidationError(
            f"No extension mapping for content type '{content_type}'"
        )
    return extension


def is_image_content_type(content_type: str) -> bool:
    """Return whether the MIME type is a supported raster image format."""
    return content_type in IMAGE_CONTENT_TYPES


def _is_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _is_heic_or_heif(data: bytes) -> bool:
    if len(data) < 12 or data[4:8] != b"ftyp":
        return False
    return data[8:12] in _HEIF_BRANDS


def validate_magic_bytes(content_type: str, data: bytes) -> None:
    """Raise when file magic bytes do not match the declared MIME type."""
    if content_type == "image/jpeg" and not data.startswith(_JPEG_MAGIC):
        raise DocumentValidationError("File is not a valid JPEG image")
    if content_type == "image/png" and not data.startswith(_PNG_MAGIC):
        raise DocumentValidationError("File is not a valid PNG image")
    if content_type == "image/webp" and not _is_webp(data):
        raise DocumentValidationError("File is not a valid WebP image")
    if content_type in ("image/heic", "image/heif") and not _is_heic_or_heif(
        data
    ):
        raise DocumentValidationError("File is not a valid HEIC/HEIF image")
    if content_type == "application/pdf" and not data.startswith(_PDF_MAGIC):
        raise DocumentValidationError("File is not a valid PDF document")
