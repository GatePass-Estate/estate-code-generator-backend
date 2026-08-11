from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from gatepass_auth import get_current_user

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.notification import NotificationRepository

router = APIRouter()


@router.post(
    "/purge-notifications",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description=(
        "Hard-delete notification rows older than the specified number of days. "
        "Minimum allowed value is NOTIFICATION_PURGE_MIN_AGE_DAYS "
        "(default 90). Root only."
    ),
)
async def purge_old_notifications(
    older_than_days: Optional[int] = Query(
        default=None,
        description="Delete notifications older than this many days. "
        "Defaults to NOTIFICATION_PURGE_MIN_AGE_DAYS if omitted.",
    ),
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    if current_user.get("role") != "root":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only root users can perform this operation.",
        )

    age = (
        older_than_days
        if older_than_days is not None
        else settings.NOTIFICATION_PURGE_MIN_AGE_DAYS
    )

    if age < settings.NOTIFICATION_PURGE_MIN_AGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"older_than_days must be at least "
                f"{settings.NOTIFICATION_PURGE_MIN_AGE_DAYS} days. "
                f"Received: {age}."
            ),
        )

    repo = NotificationRepository(ahttp_client)
    result = await repo.purge_old(older_than_days=age)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to purge notifications.",
        )
    return result
