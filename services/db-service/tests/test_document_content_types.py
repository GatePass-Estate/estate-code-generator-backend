"""Tests for shared document content-type validation."""

import pytest
from gatepass_docs import (
    DocumentValidationError,
    extension_for_content_type,
    validate_content_type,
    validate_magic_bytes,
)

_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 10
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
_WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 4
_HEIC_BYTES = b"\x00" * 4 + b"ftypheic" + b"\x00" * 20
_PDF_BYTES = b"%PDF-1.7" + b"\x00" * 10


@pytest.mark.parametrize(
    ("document_type", "content_type"),
    [
        ("profile_picture", "image/jpeg"),
        ("profile_picture", "image/png"),
        ("profile_picture", "image/webp"),
        ("profile_picture", "image/heic"),
        ("profile_picture", "image/heif"),
        ("id_card", "application/pdf"),
    ],
)
def test_validate_content_type_accepts_supported_formats(
    document_type, content_type
):
    assert validate_content_type(document_type, content_type) == content_type


def test_validate_content_type_rejects_pdf_for_profile_picture():
    with pytest.raises(DocumentValidationError):
        validate_content_type("profile_picture", "application/pdf")


@pytest.mark.parametrize(
    ("content_type", "data"),
    [
        ("image/jpeg", _JPEG_BYTES),
        ("image/png", _PNG_BYTES),
        ("image/webp", _WEBP_BYTES),
        ("image/heic", _HEIC_BYTES),
        ("image/heif", _HEIC_BYTES),
        ("application/pdf", _PDF_BYTES),
    ],
)
def test_validate_magic_bytes_accepts_supported_formats(content_type, data):
    validate_magic_bytes(content_type, data)


def test_extension_for_content_type_preserves_upload_format():
    assert extension_for_content_type("image/png") == "png"
    assert extension_for_content_type("image/webp") == "webp"
    assert extension_for_content_type("image/heic") == "heic"
