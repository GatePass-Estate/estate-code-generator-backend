from typing import Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.repositories.notification import NotificationRepository


class MaintenanceService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    async def purge_old_notifications(
        self, older_than_days: Optional[int]
    ) -> dict:
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

        result = await self.repo.purge_old(older_than_days=age)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to purge notifications.",
            )
        return result
