from fastapi import HTTPException

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler


async def check_permission(
    http_client: AsyncHttpHandler, role: str, permission_key: str
) -> bool:
    """
    Retrieves the permission for a given role and confirm if the given
    role has authorization to perform a certain action
    """
    url = (
        f"{settings.DB_SERVICE_URL}api/v1/userprofile/rolepermission/"
        f"search?role_name={role}"
    )
    response = await http_client.async_get(url)

    if not response or not response.get("items"):
        raise HTTPException(
            status_code=404,
            detail=f"Permissions not found for role '{role}'.",
        )
    permissions = response.get("items")[0]
    return permissions.get(permission_key, False)


async def get_role_permissions(
    http_client: AsyncHttpHandler, role: str
) -> dict:
    """
    Retrieves the full set of permission flags for a given role.
    """
    url = (
        f"{settings.DB_SERVICE_URL}api/v1/userprofile/rolepermission/"
        f"search?role_name={role}"
    )
    response = await http_client.async_get(url)

    if not response or not response.get("items"):
        raise HTTPException(
            status_code=404,
            detail=f"Permissions not found for role '{role}'.",
        )
    return response.get("items")[0]


async def check_status(
    user_details: dict,
) -> bool:
    """
    Confirm if the given user is verified.
    """
    status = user_details.get("status", False)
    return status
