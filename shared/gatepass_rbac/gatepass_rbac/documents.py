"""Permission checks for user document upload, view, and download."""

from __future__ import annotations

from typing import Any, Mapping

from gatepass_rbac.identity import is_owner, same_estate


def can_upload(requester: Any) -> bool:
    """Return whether the requester may upload their own documents.

    All authenticated roles may upload.

    Args:
        requester: Authenticated user. Unused; kept for a stable signature.

    Returns:
        Always ``True``.
    """
    return True


def can_view(
    requester: Any,
    target_user: Any,
    permissions: Mapping[str, bool],
) -> bool:
    """Return whether the requester may view the target user's documents.

    A user may always view their own documents. Viewing another user's
    documents requires ``can_view_other_user_documents``; doing so across
    estates additionally requires
    ``can_view_other_user_documents_in_other_estate``.

    Args:
        requester: Authenticated user.
        target_user: Document owner.
        permissions: Role permission flags.

    Returns:
        ``True`` when view is allowed.
    """
    if not is_owner(requester, target_user):
        if not permissions.get("can_view_other_user_documents", False):
            return False
    if not same_estate(requester, target_user):
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
    """Return whether the requester may download the target user's documents.

    A user may always download their own documents. Downloading another
    user's documents requires ``can_download_other_user_documents``;
    doing so across estates additionally requires
    ``can_download_other_user_documents_in_other_estate``.

    Args:
        requester: Authenticated user.
        target_user: Document owner.
        permissions: Role permission flags.

    Returns:
        ``True`` when download is allowed.
    """
    if not is_owner(requester, target_user):
        if not permissions.get("can_download_other_user_documents", False):
            return False
    if not same_estate(requester, target_user):
        if not permissions.get(
            "can_download_other_user_documents_in_other_estate", False
        ):
            return False
    return True
