"""Estate membership and resource-ownership gates."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from fastapi import HTTPException

from gatepass_rbac.identity import is_owner, same_estate
from gatepass_rbac.identity import estate_id as _estate_id
from gatepass_rbac.roles import is_root


def require_same_estate(
    left: Any,
    right: Any,
    *,
    detail: str = "Access across estates is not allowed.",
) -> None:
    """Reject the caller when the two values are not the same estate.

    Args:
        left: User mapping/object or raw estate ID.
        right: User mapping/object or raw estate ID.
        detail: HTTP 403 message on mismatch.

    Raises:
        HTTPException: 403 if the estate IDs differ.
    """
    if not same_estate(left, right):
        raise HTTPException(status_code=403, detail=detail)


def require_estate_membership(
    current_user: dict,
    estate_id: Any,
    *,
    detail: str = "User does not belong to this estate.",
) -> None:
    """Reject callers whose JWT estate does not match ``estate_id``.

    Root is not estate-bound, so this check is skipped for ``role="root"``.

    Args:
        current_user: Authenticated user dict with ``estate_id``.
        estate_id: Estate the caller must belong to.
        detail: HTTP 403 message when membership does not match.

    Raises:
        HTTPException: 403 if the JWT has no estate or it does not match.
    """
    if is_root(str(current_user.get("role", ""))):
        return
    user_estate_id = _estate_id(current_user)
    if user_estate_id is None or user_estate_id != str(estate_id):
        raise HTTPException(status_code=403, detail=detail)


def require_owner(
    actor: Any,
    owner: Any,
    *,
    detail: str = "Not allowed.",
) -> None:
    """Reject the caller unless they own the resource.

    Args:
        actor: Requester JWT dict, user object, or raw user ID.
        owner: Resource owner mapping/object or raw owner ID.
        detail: HTTP 403 message when the caller is not the owner.

    Raises:
        HTTPException: 403 if the IDs do not match.
    """
    if not is_owner(actor, owner):
        raise HTTPException(status_code=403, detail=detail)


def require_owner_or_roles(
    actor: Any,
    owner: Any,
    role: str,
    allowed_roles: Collection[str],
    *,
    detail: str,
) -> None:
    """Allow the owner or a caller whose role is in ``allowed_roles``.

    Args:
        actor: Requester JWT dict, user object, or raw user ID.
        owner: Resource owner mapping/object or raw owner ID.
        role: Caller's role.
        allowed_roles: Roles that may act without owning the resource.
        detail: HTTP 403 message when neither condition holds.

    Raises:
        HTTPException: 403 if the caller is neither owner nor allowed.
    """
    if is_owner(actor, owner) or role in allowed_roles:
        return
    raise HTTPException(status_code=403, detail=detail)
