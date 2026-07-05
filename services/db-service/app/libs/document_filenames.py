"""User-facing filenames for document stream responses."""

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
    """Prefer original upload name; else a generic photo/document fallback."""
    if original_filename:
        safe_name = original_filename.replace("\\", "/").split("/")[-1].strip()
        if safe_name:
            return safe_name

    extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")
    if content_type == "image/jpeg":
        return f"photo.{extension}"
    return f"document.{extension}"
