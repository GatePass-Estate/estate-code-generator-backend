from __future__ import annotations

from typing import Any


def _document_type_value(document_type: Any) -> str:
    value = getattr(document_type, "value", document_type)
    return str(value)


def requires_admin_approval(document_type: Any, uploader_role: str) -> bool:
    """Return whether an upload must be staged pending admin approval."""
    if _document_type_value(document_type) != "id_card":
        return False
    return uploader_role in ("resident", "security", "guest")
