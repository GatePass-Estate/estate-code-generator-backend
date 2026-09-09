"""Permission helpers for access-log viewing."""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException

from gatepass_rbac.identity import is_owner, same_estate


def can_view_logs(
    requester: Any,
    target_user: Any,
    permissions: Mapping[str, bool],
) -> bool:
    """Return whether the requester may view the target user's logs.

    A user may always view their own logs. Viewing another user's logs
    requires ``can_view_other_user_logs``; doing so across estates
    additionally requires ``can_view_other_user_logs_in_other_estate``.

    Args:
        requester: Authenticated user.
        target_user: Log owner.
        permissions: Role permission flags.

    Returns:
        ``True`` when log view is allowed.
    """
    if not is_owner(requester, target_user):
        if not permissions.get("can_view_other_user_logs", False):
            return False
    if not same_estate(requester, target_user):
        if not permissions.get(
            "can_view_other_user_logs_in_other_estate", False
        ):
            return False
    return True


def resolve_estate_log_scope(
    requester: Mapping[str, Any],
    permissions: Mapping[str, bool],
) -> str | None:
    """Authorize an estate-wide log request and return the estate scope.

    Args:
        requester: Authenticated user with ``estate_id`` and ``role``.
        permissions: Role permission flags.

    Returns:
        The requester's estate ID when they may only view their own
        estate, or ``None`` when they may view all estates.

    Raises:
        HTTPException: 403 if the requester may not view others' logs
            or has no estate when a scope is required.
    """
    if not permissions.get("can_view_other_user_logs", False):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view these logs.",
        )
    if permissions.get("can_view_other_user_logs_in_other_estate", False):
        return None
    estate = requester.get("estate_id")
    if not estate:
        raise HTTPException(
            status_code=403,
            detail="No estate is associated with your account.",
        )
    return str(estate)
