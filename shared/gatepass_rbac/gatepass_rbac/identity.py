"""Normalize user and estate identifiers from JWT dicts or domain objects."""

from __future__ import annotations

from typing import Any, Mapping


def user_id(value: Any) -> str:
    """Return a string user ID from a mapping, object, or raw value.

    Args:
        value: A JWT/user dict with ``id``, an object with ``.id``,
            or a raw UUID/string.

    Returns:
        The identifier as a string.
    """
    if isinstance(value, Mapping):
        return str(value["id"])
    raw = getattr(value, "id", None)
    if raw is not None and not isinstance(value, (str, bytes)):
        return str(raw)
    return str(value)


def estate_id(value: Any) -> str | None:
    """Return a string estate ID from a mapping, object, or raw value.

    Args:
        value: A JWT/user dict with ``estate_id``, an object with
            ``.estate_id``, a raw UUID/string, or ``None``.

    Returns:
        The estate identifier as a string, or ``None`` if missing.
    """
    if value is None:
        return None
    if isinstance(value, Mapping):
        raw = value.get("estate_id")
    elif hasattr(value, "estate_id"):
        raw = getattr(value, "estate_id", None)
    else:
        raw = value
    if raw is None:
        return None
    return str(raw)


def is_owner(actor: Any, owner: Any) -> bool:
    """Return whether ``actor`` and ``owner`` resolve to the same user ID.

    Args:
        actor: Requester JWT dict, user object, or raw user ID.
        owner: Resource owner mapping/object or raw owner ID.

    Returns:
        ``True`` when both sides identify the same user.
    """
    return user_id(actor) == user_id(owner)


def same_estate(left: Any, right: Any) -> bool:
    """Return whether two values refer to the same estate.

    Returns ``False`` when either side has no estate ID so that
    unaffiliated users never pass an estate-scoping check.

    Args:
        left: User mapping/object or raw estate ID.
        right: User mapping/object or raw estate ID.

    Returns:
        ``True`` when the normalized estate IDs are equal and non-None.
    """
    left_id = estate_id(left)
    right_id = estate_id(right)
    if left_id is None or right_id is None:
        return False
    return left_id == right_id
