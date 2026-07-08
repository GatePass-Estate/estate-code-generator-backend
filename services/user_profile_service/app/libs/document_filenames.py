"""User-facing filenames for document view/download streams."""

from __future__ import annotations

from gatepass_docs import extension_for_content_type, is_image_content_type


def stream_filename(
    *,
    content_type: str,
    original_filename: str | None,
) -> str:
    """
    Build a download/view filename without internal ids or document types.

    Prefers the sanitized original upload name; otherwise a generic fallback
    derived from content type only (e.g. photo.png, document.pdf).
    """
    if original_filename:
        safe_name = original_filename.replace("\\", "/").split("/")[-1].strip()
        if safe_name:
            return safe_name

    extension = extension_for_content_type(content_type)
    if is_image_content_type(content_type):
        return f"photo.{extension}"
    return f"document.{extension}"
