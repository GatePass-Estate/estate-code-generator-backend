"""Permission helpers for code-service log viewing endpoints."""

from __future__ import annotations

from typing import Any, Mapping


def _user_id(user: Any) -> str:
    """Normalize a JWT dict or user detail mapping to a string user ID."""
    if isinstance(user, Mapping):
        return str(user["id"])
    return str(user.id)


def _estate_id(user: Any) -> str | None:
    """Normalize a JWT dict or user detail mapping to a string estate ID."""
    if isinstance(user, Mapping):
        value = user.get("estate_id")
    else:
        value = getattr(user, "estate_id", None)
    if value is None:
        return None
    return str(value)


def can_view_logs(
    requester: Any,
    target_user: Any,
    permissions: Mapping[str, bool],
) -> bool:
    """Return whether the requester may view the target user's logs.

    A user may always view their own logs. Viewing another user's logs
    requires ``can_view_other_user_logs``; doing so across estates
    additionally requires ``can_view_other_user_logs_in_other_estate``.
    """
    if _user_id(requester) != _user_id(target_user):
        if not permissions.get("can_view_other_user_logs", False):
            return False
    if _estate_id(target_user) != _estate_id(requester):
        if not permissions.get(
            "can_view_other_user_logs_in_other_estate", False
        ):
            return False
    return True
