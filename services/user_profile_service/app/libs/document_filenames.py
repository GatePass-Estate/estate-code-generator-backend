"""User-facing filenames for document view/download streams."""

from __future__ import annotations

_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "application/pdf": "pdf",
}


def stream_filename(
    *,
    content_type: str,
    original_filename: str | None,
) -> str:
    """
    Build a download/view filename without internal ids or document types.

    Prefers the sanitized original upload name; otherwise a generic fallback
    derived from content type only (e.g. photo.jpg, document.pdf).
    """
    if original_filename:
        safe_name = original_filename.replace("\\", "/").split("/")[-1].strip()
        if safe_name:
            return safe_name

    extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")
    if content_type == "image/jpeg":
        return f"photo.{extension}"
    return f"document.{extension}"
