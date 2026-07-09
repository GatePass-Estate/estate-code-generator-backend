from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.libs.auth_helpers import (
    get_auth_service,
    get_client_ip,
    get_device_name,
    get_user_service,
)
from app.core.config import settings
from app.libs.notify import (
    fire_deactivate_device_token_by_session,
    fire_notify,
    fire_notify_critical,
    fire_remove_device_token_by_session,
    fire_remove_device_token_by_user,
)
from app.schemas.auth import (
    AcceptTosRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    SessionListResponse,
    TwoFADisableRequest,
    TwoFAEnableRequest,
    TwoFAEnableResponse,
    TwoFARecoverRequest,
    TwoFARegenerateCodesRequest,
    TwoFARegenerateCodesResponse,
    TwoFASetupResponse,
    TwoFAVerifyRequest,
)
from app.schemas.user import SetPasswordResponse
from app.services.auth import (
    AuthService,
    get_current_user_unverified as get_current_user,
)
from app.services.token import decode_2fa_pending_token
from app.services.user import UserService

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: LoginRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Authenticates a user. If 2FA is enabled and the IP is unfamiliar,
    returns a 2FA-pending token instead of an access token.
    If TOS acceptance is pending, returns a tos_pending token.
    """
    return await auth_service.login(
        email=request.email,
        password=request.password,
        estate_id=str(request.estate_id) if request.estate_id else None,
        ip=get_client_ip(http_request),
        device=get_device_name(http_request),
    )


@router.post("/2fa/verify", response_model=LoginResponse)
async def verify_2fa(
    request: TwoFAVerifyRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Completes 2FA login by verifying a TOTP code.
    Creates a session (is_2fa_verified=True) and returns an access token.
    """
    ip = get_client_ip(http_request)
    device = get_device_name(http_request)
    result = await auth_service.verify_2fa(
        two_fa_token=request.two_fa_token,
        code=request.code,
        ip=ip,
        device=device,
    )
    try:
        user_id = decode_2fa_pending_token(request.two_fa_token)
        background_tasks.add_task(
            fire_notify,
            {
                "type": "LOGIN_NEW_DEVICE",
                "title": "New device login",
                "body": "Your account was accessed from a new device.",
                "recipient_user_ids": [str(user_id)],
                "metadata": {"ip_address": ip or "", "device_name": device},
            },
        )
    except Exception:
        pass
    return result


@router.post("/2fa/recover", response_model=LoginResponse)
async def recover_2fa(
    request: TwoFARecoverRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Logs in using a one-time recovery code. Disables 2FA on the account.
    Creates a session and returns an access token.
    """
    result = await auth_service.recover_2fa(
        two_fa_token=request.two_fa_token,
        recovery_code=request.recovery_code,
        ip=get_client_ip(http_request),
        device=get_device_name(http_request),
    )
    try:
        user_id = decode_2fa_pending_token(request.two_fa_token)
        background_tasks.add_task(
            fire_notify,
            {
                "type": "TWO_FA_RECOVERY_USED",
                "title": "2FA recovery code used",
                "body": (
                    "A recovery code was used to access your account "
                    "and 2FA has been disabled."
                ),
                "recipient_user_ids": [str(user_id)],
            },
        )
    except Exception:
        pass
    return result


@router.post("/accept-tos", response_model=LoginResponse)
async def accept_tos(
    request: AcceptTosRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """
    Accepts the current Terms of Service and returns a full access token.
    Creates a new session at this point if one doesn't exist yet.
    """
    return await auth_service.accept_tos(
        tos_token=request.tos_token,
        ip=get_client_ip(http_request),
        device=get_device_name(http_request),
    )


@router.post("/logout")
async def logout(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Soft-deletes the current session, invalidating this JWT immediately."""
    result = await auth_service.logout(current_user["session_id"])
    background_tasks.add_task(
        fire_deactivate_device_token_by_session, current_user["session_id"]
    )
    return result


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> SessionListResponse:
    """Lists all active sessions for the current user."""
    return await auth_service.list_sessions(current_user["id"])


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Soft-deletes a specific session. Must belong to the current user."""
    result = await auth_service.revoke_session(
        session_id=session_id,
        user_id=current_user["id"],
    )
    background_tasks.add_task(
        fire_notify,
        {
            "type": "SESSION_REVOKED",
            "title": "Session revoked",
            "body": "One of your active sessions has been revoked.",
            "recipient_user_ids": [current_user["id"]],
            "metadata": {"session_id": session_id},
        },
    )
    background_tasks.add_task(fire_remove_device_token_by_session, session_id)
    return result


@router.delete("/sessions")
async def revoke_all_sessions(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Soft-deletes ALL sessions for the current user."""
    result = await auth_service.revoke_all_sessions(current_user["id"])
    background_tasks.add_task(
        fire_remove_device_token_by_user, current_user["id"]
    )
    return result


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> TwoFASetupResponse:
    """
    Generates a TOTP secret and returns the provisioning URI for QR code.
    2FA is NOT enabled until POST /auth/2fa/enable is called with a valid code.
    """
    return await auth_service.setup_2fa(current_user["id"])


@router.post("/2fa/enable", response_model=TwoFAEnableResponse)
async def enable_2fa(
    request: TwoFAEnableRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> TwoFAEnableResponse:
    """
    Confirms 2FA setup with a TOTP code and enables it on the account.
    Returns 8 one-time recovery codes — store them securely, shown only once.
    """
    result = await auth_service.enable_2fa(current_user["id"], request.code)
    background_tasks.add_task(
        fire_notify,
        {
            "type": "TWO_FA_ENABLED",
            "title": "Two-factor authentication enabled",
            "body": "2FA has been enabled on your account.",
            "recipient_user_ids": [current_user["id"]],
        },
    )
    return result


@router.delete("/2fa/disable")
async def disable_2fa(
    request: TwoFADisableRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Disables 2FA after verifying the current TOTP code."""
    await auth_service.disable_2fa(current_user["id"], request.code)
    background_tasks.add_task(
        fire_notify,
        {
            "type": "TWO_FA_DISABLED",
            "title": "Two-factor authentication disabled",
            "body": "2FA has been disabled on your account.",
            "recipient_user_ids": [current_user["id"]],
        },
    )
    return {"success": True, "message": "2FA disabled."}


@router.post(
    "/2fa/regenerate-codes",
    response_model=TwoFARegenerateCodesResponse,
)
async def regenerate_recovery_codes(
    request: TwoFARegenerateCodesRequest,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> TwoFARegenerateCodesResponse:
    """
    Regenerates recovery codes after verifying the current TOTP code.
    Old codes are invalidated. New codes shown only once.
    """
    return await auth_service.regenerate_recovery_codes(
        current_user["id"], request.code
    )


@router.post("/forgot-password", response_model=SetPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    user_service: UserService = Depends(get_user_service),
) -> SetPasswordResponse:
    """
    Initiates the forgot password flow.

    Sends a password reset link to the provided email if an active account
    exists. Always returns success to prevent email enumeration.
    Raises 502 if the notification service is unreachable and the account
    exists (reset link cannot be delivered).
    """
    from urllib.parse import urlencode

    estate_id = str(request.estate_id) if request.estate_id else None
    result = await user_service.forgot_password(request.email, estate_id)
    if result:
        user_id, token = result
        query = urlencode({"token": token})
        reset_url = f"{settings.FRONTEND_BASE_URL}/auth/reset-password?{query}"
        await fire_notify_critical(
            {
                "type": "FORGOT_PASSWORD",
                "title": "Reset your password",
                "body": (
                    "We received a request to reset your GatePass password."
                ),
                "recipient_user_ids": [user_id],
                "metadata": {"reset_url": reset_url},
            }
        )

    return SetPasswordResponse(
        success=True,
        message=(
            "If an account with that email exists, "
            "a password reset link has been sent."
        ),
    )
