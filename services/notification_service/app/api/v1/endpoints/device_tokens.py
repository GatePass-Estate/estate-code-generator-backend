from fastapi import APIRouter, Depends, HTTPException, status
from gatepass_auth import get_current_user

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.device_token import DeviceTokenRepository
from app.schemas.device_token import (
    RegisterDeviceTokenRequest,
    RegisterDeviceTokenResponse,
)

router = APIRouter()


@router.post("", response_model=RegisterDeviceTokenResponse)
async def register_device_token(
    payload: RegisterDeviceTokenRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = DeviceTokenRepository(ahttp_client)
    result = await repo.register(
        user_id=current_user["id"],
        token=payload.token,
        platform=payload.platform,
        session_id=payload.session_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to register device token",
        )
    return result


@router.delete("/by-token/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device_token(
    token: str,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    repo = DeviceTokenRepository(ahttp_client)
    user_tokens = await repo.get_by_user(
        user_id=current_user["id"], active_only=False
    )
    items = (
        user_tokens.get("items") or user_tokens.get("data") or []
        if user_tokens
        else []
    )
    if not any(t.get("token") == token for t in items):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to the current user.",
        )
    await repo.remove_by_token(token=token)
