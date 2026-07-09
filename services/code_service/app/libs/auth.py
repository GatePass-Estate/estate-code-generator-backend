from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from gatepass_auth import get_current_user  # noqa: F401


async def get_user_details(
    http_client: AsyncHttpHandler,
    user_id: str,
) -> bool:
    """
    Retrieves user details using a given user_id.
    """
    url = f"{settings.DB_SERVICE_URL}api/v1/userprofile/users/{user_id}"
    return await http_client.async_get(url)
