from fastapi import APIRouter, Depends, HTTPException, status
from gatepass_auth import get_current_user

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.notification_preference import (
    NotificationPreferenceRepository,
)
from app.schemas.notification import (
    ListPreferencesResponse,
    NotificationType,
    PreferenceResponse,
    UpdatePreferenceRequest,
)

router = APIRouter()


@router.get("", response_model=ListPreferencesResponse)
async def list_preferences(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationPreferenceRepository(ahttp_client)
    result = await repo.get_by_user(user_id=current_user["id"])
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch preferences",
        )
    return result


@router.put("/{notification_type}", response_model=PreferenceResponse)
async def upsert_preference(
    notification_type: NotificationType,
    payload: UpdatePreferenceRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = NotificationPreferenceRepository(ahttp_client)
    result = await repo.upsert(
        user_id=current_user["id"],
        notification_type=notification_type,
        push_enabled=payload.push_enabled,
        email_enabled=payload.email_enabled,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upsert preference",
        )
    return result
