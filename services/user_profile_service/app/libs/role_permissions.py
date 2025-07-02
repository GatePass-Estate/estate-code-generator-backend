from app.repositories.user import UserRepository
from app.libs.http_handler import AsyncHttpHandler


async def check_permission(
    http_client: AsyncHttpHandler, role: str, permission_key: str
) -> bool:
    repo = UserRepository(http_client)
    permissions = await repo.get_role_permissions(role)
    return permissions.get(permission_key, False)
