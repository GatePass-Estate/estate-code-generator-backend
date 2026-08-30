import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.device_token import DeviceTokenRepository
from app.schemas.internal import InternalNotifyRequest
from app.schemas.feedback import FeedbackEmailRequest
from app.services.email import send_user_feedback_email
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
    processes fan-out in a background task. Recipients are either an
    explicit ``recipient_user_ids`` list or a ``fan_out`` of estate roles.
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


@router.post(
    "/feedback",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_internal_key)],
)
async def send_feedback(
    payload: FeedbackEmailRequest,
    background_tasks: BackgroundTasks,
):
    """
    Forward user-submitted feedback as an email to the GatePass team.

    Protected by X-Internal-Key header. Returns 202 immediately and
    sends the email in a background task.
    """
    background_tasks.add_task(
        send_user_feedback_email,
        feedback_type=payload.feedback_type,
        user_name=payload.user_name,
        user_email=payload.user_email,
        estate_name=payload.estate_name,
        rating=payload.rating,
        liked=payload.liked,
        improvement=payload.improvement,
        description=payload.description,
        attachment_url=payload.attachment_url,
    )
    return {"status": "accepted"}
