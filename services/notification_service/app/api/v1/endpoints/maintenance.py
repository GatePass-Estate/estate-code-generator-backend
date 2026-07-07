from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from gatepass_auth import get_current_user

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.notification import NotificationRepository
from app.services.maintenance import MaintenanceService

router = APIRouter()


@router.post(
    "/purge-notifications",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    description=(
        "Hard-delete notification rows older than the specified number of days. "
        f"Minimum allowed value is NOTIFICATION_PURGE_MIN_AGE_DAYS "
        f"(default {settings.NOTIFICATION_PURGE_MIN_AGE_DAYS}). Root only."
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

    service = MaintenanceService(repo=NotificationRepository(ahttp_client))
    return await service.purge_old_notifications(older_than_days)
