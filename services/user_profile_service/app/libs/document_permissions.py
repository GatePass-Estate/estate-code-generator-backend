"""Permission checks for user document upload, view, and download."""

from __future__ import annotations

from typing import Any, Mapping


def _user_id(user: Any) -> str:
    if isinstance(user, Mapping):
        return str(user["id"])
    return str(user.id)


def _estate_id(user: Any) -> str | None:
    if isinstance(user, Mapping):
        value = user.get("estate_id")
    else:
        value = getattr(user, "estate_id", None)
    if value is None:
        return None
    return str(value)


def can_upload(requester: Any) -> bool:
    """All authenticated roles may upload their own documents."""
    return True


def can_view(
    requester: Any,
    target_user: Any,
    permissions: Mapping[str, bool],
) -> bool:
    if _user_id(requester) != _user_id(target_user):
        if not permissions.get("can_view_other_user_documents", False):
            return False
    if _estate_id(target_user) != _estate_id(requester):
        if not permissions.get(
            "can_view_other_user_documents_in_other_estate", False
        ):
            return False
    return True


def can_download(
    requester: Any,
    target_user: Any,
    permissions: Mapping[str, bool],
) -> bool:
    if _user_id(requester) != _user_id(target_user):
        if not permissions.get("can_download_other_user_documents", False):
            return False
    if _estate_id(target_user) != _estate_id(requester):
        if not permissions.get(
            "can_download_other_user_documents_in_other_estate", False
        ):
            return False
    return True
