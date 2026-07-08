import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.device_token import DeviceTokenRepository
from app.schemas.internal import InternalNotifyRequest
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()

_internal_key_scheme = APIKeyHeader(name="X-Internal-Key", auto_error=False)


def _verify_internal_key(
    key: str = Depends(_internal_key_scheme),
) -> None:
    if not key or key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing internal API key",
        )


@router.post(
    "/notify",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_internal_key)],
)
async def internal_notify(
    payload: InternalNotifyRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """
    Fire-and-forget notification dispatch.

    Protected by X-Internal-Key header. Returns 202 immediately and
    processes fan-out in a background task.
    """
    service = NotificationService(ahttp_client)
    background_tasks.add_task(service.process, payload)
    return {"status": "accepted"}


@router.patch(
    "/device-tokens/deactivate-by-session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_verify_internal_key)],
)
async def deactivate_device_tokens_by_session(
    session_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """Soft-deactivate device tokens for a session (called on self-logout)."""
    repo = DeviceTokenRepository(ahttp_client)
    await repo.deactivate_by_session(session_id=session_id)


@router.delete(
    "/device-tokens/by-session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_verify_internal_key)],
)
async def remove_device_tokens_by_session(
    session_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """Hard-delete device tokens for a session (called on explicit session revoke)."""
    repo = DeviceTokenRepository(ahttp_client)
    await repo.remove_by_session(session_id=session_id)


@router.delete(
    "/device-tokens/by-user/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_verify_internal_key)],
)
async def remove_device_tokens_by_user(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """Remove all device tokens for a user (called on revoke-all-sessions)."""
    repo = DeviceTokenRepository(ahttp_client)
    await repo.remove_by_user(user_id=user_id)
