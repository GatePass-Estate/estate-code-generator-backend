"""Tests for user-facing stream filenames."""

from app.libs.document_filenames import stream_filename


def test_prefers_sanitized_original_filename():
    assert (
        stream_filename(
            content_type="image/jpeg",
            original_filename="my passport.jpg",
        )
        == "my passport.jpg"
    )


def test_strips_path_from_original_filename():
    assert (
        stream_filename(
            content_type="application/pdf",
            original_filename="/tmp/uploads/id-card.pdf",
        )
        == "id-card.pdf"
    )


def test_jpeg_fallback_is_photo():
    assert (
        stream_filename(content_type="image/jpeg", original_filename=None)
        == "photo.jpg"
    )


def test_png_fallback_is_photo():
    assert (
        stream_filename(content_type="image/png", original_filename=None)
        == "photo.png"
    )


def test_heic_fallback_is_photo():
    assert (
        stream_filename(content_type="image/heic", original_filename=None)
        == "photo.heic"
    )


def test_pdf_fallback_is_document():
    assert (
        stream_filename(content_type="application/pdf", original_filename=None)
        == "document.pdf"
    )


def test_no_internal_ids_in_fallback():
    name = stream_filename(content_type="image/jpeg", original_filename=None)
    assert "profile_picture" not in name
    assert "ea544461" not in name
