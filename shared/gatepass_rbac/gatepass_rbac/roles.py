"""Role-set confirmation used before allowing an action."""

from __future__ import annotations

from collections.abc import Collection

from fastapi import HTTPException

ADMIN_ROLES: frozenset[str] = frozenset({"admin", "primary_admin", "root"})
ROOT_ROLE = "root"

ROLE_RANK: dict[str, int] = {
    "root": 5,
    "primary_admin": 4,
    "admin": 3,
    "resident": 2,
    "security": 2,
    "guest": 1,
}


def is_root(role: str) -> bool:
    """Return whether ``role`` is root."""
    return str(role).lower() == ROOT_ROLE


def is_admin(role: str) -> bool:
    """Return whether ``role`` is an admin-tier role.

    Args:
        role: Role name from the JWT or user record.

    Returns:
        ``True`` for ``admin``, ``primary_admin``, or ``root``.
    """
    return role in ADMIN_ROLES


def require_roles(
    role: str,
    allowed: Collection[str],
    *,
    detail: str = "You are not authorized to perform this action.",
) -> None:
    """Reject the caller unless ``role`` is in ``allowed``.

    Args:
        role: Caller's role.
        allowed: Roles that may proceed.
        detail: HTTP 403 message when the role is not allowed.

    Raises:
        HTTPException: 403 if ``role`` is not in ``allowed``.
    """
    if role not in allowed:
        raise HTTPException(status_code=403, detail=detail)


def require_admin(
    role: str,
    *,
    detail: str = "Only admins can access this resource.",
) -> None:
    """Reject the caller unless they have an admin-tier role.

    Args:
        role: Caller's role.
        detail: HTTP 403 message when the role is not admin-tier.

    Raises:
        HTTPException: 403 if ``role`` is not admin-tier.
    """
    require_roles(role, ADMIN_ROLES, detail=detail)


def deny_roles(
    role: str,
    blocked: Collection[str],
    *,
    detail: str,
) -> None:
    """Reject the caller when ``role`` is in ``blocked``.

    Comparison is case-insensitive.

    Args:
        role: Caller's role.
        blocked: Roles that must not proceed.
        detail: HTTP 403 message when the role is blocked.

    Raises:
        HTTPException: 403 if ``role`` is blocked.
    """
    if str(role).lower() in {item.lower() for item in blocked}:
        raise HTTPException(status_code=403, detail=detail)


def can_act_on_role(actor_role: str, target_role: str) -> bool:
    """Return whether ``actor_role`` outranks ``target_role``.

    Used for destructive actions such as closing another account.

    Args:
        actor_role: Role of the caller.
        target_role: Role of the target user.

    Returns:
        ``True`` when the actor's rank is strictly higher.
    """
    return ROLE_RANK.get(actor_role, 0) > ROLE_RANK.get(target_role, 0)


def require_higher_rank(
    actor_role: str,
    target_role: str,
    *,
    detail: str = "You cannot act on an account of equal or higher rank.",
) -> None:
    """Reject the caller unless their role outranks the target.

    Args:
        actor_role: Role of the caller.
        target_role: Role of the target user.
        detail: HTTP 403 message when the ranks are not strictly ordered.

    Raises:
        HTTPException: 403 if the actor does not outrank the target.
    """
    if not can_act_on_role(actor_role, target_role):
        raise HTTPException(status_code=403, detail=detail)


def check_status(user_details: dict) -> bool:
    """Return whether the user account is marked verified/active.

    Args:
        user_details: User payload that may include a ``status`` flag.

    Returns:
        The ``status`` value, or ``False`` when missing.
    """
    return bool(user_details.get("status", False))
