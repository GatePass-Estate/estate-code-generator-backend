"""Fetch ``role_permission`` flags from db-service and test a single key."""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import HTTPException

from gatepass_rbac.config import DB_SERVICE_URL


class AsyncGetter(Protocol):
    """Minimal HTTP client used to load role permissions."""

    async def async_get(self, url: str) -> Any:
        """Perform a GET and return the decoded JSON body."""


async def get_role_permissions(http_client: AsyncGetter, role: str) -> dict:
    """Return the permission flags stored for ``role``.

    Args:
        http_client: Client with ``async_get``.
        role: Role name, for example ``admin``.

    Returns:
        The first matching ``role_permission`` row.

    Raises:
        HTTPException: 404 if no permission row exists for the role.
    """
    url = (
        f"{DB_SERVICE_URL}api/v1/userprofile/rolepermission/"
        f"search?role_name={role}"
    )
    response = await http_client.async_get(url)

    if not response or not response.get("items"):
        raise HTTPException(
            status_code=404,
            detail=f"Permissions not found for role '{role}'.",
        )
    return response.get("items")[0]


async def check_permission(
    http_client: AsyncGetter, role: str, permission_key: str
) -> bool:
    """Return whether ``role`` has the named permission flag.

    Args:
        http_client: Client with ``async_get``.
        role: Role name, for example ``admin``.
        permission_key: Flag on the role_permission row, for example
            ``can_register_users``.

    Returns:
        ``True`` when the flag is set; ``False`` when missing or unset.

    Raises:
        HTTPException: 404 if no permission row exists for the role.
    """
    permissions = await get_role_permissions(http_client, role)
    return bool(permissions.get(permission_key, False))
