from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.core.config import settings
from app.libs.auth_helpers import (
    get_client_ip,
    get_device_name,
    make_user_service,
    session_expires_at,
)
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.session import SessionRepository
from app.repositories.totp_recovery_codes import TotpRecoveryCodesRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    AcceptTosRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    SessionListResponse,
    SessionResponse,
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
from app.services.auth import generate_access_token, get_current_user
from app.services.email import send_password_reset_email
from app.services.token import (
    decode_2fa_pending_token,
    generate_2fa_pending_token,
    generate_tos_pending_token,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login_user(
    request: LoginRequest,
    http_request: Request,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Authenticates a user. If 2FA is enabled and the IP is unfamiliar,
    returns a 2FA-pending token instead of an access token.
    If TOS acceptance is pending, returns a tos_pending token.
    """
    repo = UserRepository(ahttp_client)
    session_repo = SessionRepository(ahttp_client)
    estate_id = str(request.estate_id) if request.estate_id else None
    user = await repo.authenticate_user(
        request.email, request.password, estate_id
    )

    ip = get_client_ip(http_request)
    device = get_device_name(http_request)

    totp_enabled = user.get("totp_enabled") or False
    if totp_enabled:
        # Familiar IP: 2FA-verified session from this IP in last 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        existing = await session_repo.search_sessions(
            user_id=str(user["id"]),
            ip_address=ip,
            is_2fa_verified=True,
            last_active_after=cutoff,
        )
        if not existing.get("items"):
            # Unfamiliar IP — return 2FA-pending token, no session yet
            two_fa_token = generate_2fa_pending_token(user["id"])
            return LoginResponse(
                success=True,
                requires_2fa=True,
                two_fa_token=two_fa_token,
            )
        # Familiar IP — 2FA already satisfied
        session = await session_repo.create_session(
            user_id=str(user["id"]),
            ip_address=ip,
            device_name=device,
            expires_at=session_expires_at(),
            is_2fa_verified=True,
        )
    else:
        session = await session_repo.create_session(
            user_id=str(user["id"]),
            ip_address=ip,
            device_name=device,
            expires_at=session_expires_at(),
            is_2fa_verified=False,
        )

    session_id = session["id"]

    if user.get("tos_accepted_version") != settings.TOS_VERSION:
        tos_token = generate_tos_pending_token(user["id"])
        return LoginResponse(
            success=True,
            role=user["role"],
            access_token=tos_token,
            requires_tos_acceptance=True,
        )

    token = generate_access_token(user, session_id)
    return LoginResponse(success=True, role=user["role"], access_token=token)


@router.post("/2fa/verify", response_model=LoginResponse)
async def verify_2fa(
    request: TwoFAVerifyRequest,
    http_request: Request,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Completes 2FA login by verifying a TOTP code.
    Creates a session (is_2fa_verified=True) and returns an access token.
    """
    try:
        user_id = decode_2fa_pending_token(request.two_fa_token)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid or expired 2FA token."
        )

    user_repo = UserRepository(ahttp_client)
    user = await user_repo.get_user_by_id(str(user_id))
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found.")

    service = make_user_service(ahttp_client)
    if not await service.verify_totp_code(str(user_id), request.code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code.")

    ip = get_client_ip(http_request)
    device = get_device_name(http_request)
    session_repo = SessionRepository(ahttp_client)
    session = await session_repo.create_session(
        user_id=str(user_id),
        ip_address=ip,
        device_name=device,
        expires_at=session_expires_at(),
        is_2fa_verified=True,
    )

    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "estate_id": str(user.estate_id) if user.estate_id else None,
        "tos_accepted_version": user.tos_accepted_version,
    }

    if user_dict.get("tos_accepted_version") != settings.TOS_VERSION:
        tos_token = generate_tos_pending_token(user_dict["id"])
        return LoginResponse(
            success=True,
            role=user_dict["role"],
            access_token=tos_token,
            requires_tos_acceptance=True,
        )

    token = generate_access_token(user_dict, session["id"])
    return LoginResponse(
        success=True, role=user_dict["role"], access_token=token
    )


@router.post("/2fa/recover", response_model=LoginResponse)
async def recover_2fa(
    request: TwoFARecoverRequest,
    http_request: Request,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Logs in using a one-time recovery code. Disables 2FA on the account.
    Creates a session and returns an access token.
    """
    service = make_user_service(ahttp_client)
    totp_recovery_repo = TotpRecoveryCodesRepository(ahttp_client)

    user_dict = await service.recover_with_code(
        request.two_fa_token, request.recovery_code, totp_recovery_repo
    )

    ip = get_client_ip(http_request)
    device = get_device_name(http_request)
    session_repo = SessionRepository(ahttp_client)
    session = await session_repo.create_session(
        user_id=user_dict["id"],
        ip_address=ip,
        device_name=device,
        expires_at=session_expires_at(),
        is_2fa_verified=True,
    )

    if user_dict.get("tos_accepted_version") != settings.TOS_VERSION:
        tos_token = generate_tos_pending_token(user_dict["id"])
        return LoginResponse(
            success=True,
            role=user_dict["role"],
            access_token=tos_token,
            requires_tos_acceptance=True,
        )

    token = generate_access_token(user_dict, session["id"])
    return LoginResponse(
        success=True, role=user_dict["role"], access_token=token
    )


@router.post("/accept-tos", response_model=LoginResponse)
async def accept_tos(
    request: AcceptTosRequest,
    http_request: Request,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> LoginResponse:
    """
    Accepts the current Terms of Service and returns a full access token.
    Creates a new session at this point if one doesn't exist yet.
    """
    service = make_user_service(ahttp_client)
    user = await service.accept_tos(request.tos_token)

    ip = get_client_ip(http_request)
    device = get_device_name(http_request)
    session_repo = SessionRepository(ahttp_client)
    session = await session_repo.create_session(
        user_id=user["id"],
        ip_address=ip,
        device_name=device,
        expires_at=session_expires_at(),
        is_2fa_verified=user.get("totp_enabled", False),
    )

    token = generate_access_token(user, session["id"])
    return LoginResponse(
        success=True,
        role=user["role"],
        access_token=token,
        requires_tos_acceptance=False,
    )


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> dict:
    """Soft-deletes the current session, invalidating this JWT immediately."""
    session_id = current_user.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="No session associated with this token.",
        )
    session_repo = SessionRepository(ahttp_client)
    await session_repo.delete_session(session_id)
    return {"success": True, "message": "Logged out successfully."}


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> SessionListResponse:
    """Lists all active sessions for the current user."""
    session_repo = SessionRepository(ahttp_client)
    result = await session_repo.search_sessions(
        user_id=current_user["id"], limit=100
    )
    items = [
        SessionResponse(
            id=s["id"],
            device_name=s.get("device_name"),
            ip_address=s.get("ip_address"),
            last_active_at=s["last_active_at"],
            expires_at=s["expires_at"],
            is_2fa_verified=s.get("is_2fa_verified", False),
            created_at=s["created_at"],
        )
        for s in result.get("items", [])
        if not s.get("is_deleted")
    ]
    return SessionListResponse(items=items, total=len(items))


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> dict:
    """Soft-deletes a specific session. Must belong to the current user."""
    session_repo = SessionRepository(ahttp_client)
    session = await session_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if str(session.get("user_id")) != current_user["id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only revoke your own sessions.",
        )
    await session_repo.delete_session(session_id)
    return {"success": True}


@router.delete("/sessions")
async def revoke_all_sessions(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> dict:
    """Soft-deletes ALL sessions for the current user."""
    session_repo = SessionRepository(ahttp_client)
    await session_repo.delete_all_sessions_for_user(current_user["id"])
    return {"success": True, "message": "All sessions revoked."}


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> TwoFASetupResponse:
    """
    Generates a TOTP secret and returns the provisioning URI for QR code.
    2FA is NOT enabled until POST /auth/2fa/enable is called with a valid code.
    """
    service = make_user_service(ahttp_client)
    result = await service.setup_2fa(current_user["id"])
    return TwoFASetupResponse(**result)


@router.post("/2fa/enable", response_model=TwoFAEnableResponse)
async def enable_2fa(
    request: TwoFAEnableRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> TwoFAEnableResponse:
    """
    Confirms 2FA setup with a TOTP code and enables it on the account.
    Returns 8 one-time recovery codes — store them securely, shown only once.
    """
    service = make_user_service(ahttp_client)
    totp_recovery_repo = TotpRecoveryCodesRepository(ahttp_client)
    codes = await service.enable_2fa(
        current_user["id"], request.code, totp_recovery_repo
    )
    return TwoFAEnableResponse(recovery_codes=codes)


@router.delete("/2fa/disable")
async def disable_2fa(
    request: TwoFADisableRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> dict:
    """Disables 2FA after verifying the current TOTP code."""
    service = make_user_service(ahttp_client)
    totp_recovery_repo = TotpRecoveryCodesRepository(ahttp_client)
    await service.disable_2fa(
        current_user["id"], request.code, totp_recovery_repo
    )
    return {"success": True, "message": "2FA disabled."}


@router.post(
    "/2fa/regenerate-codes",
    response_model=TwoFARegenerateCodesResponse,
)
async def regenerate_recovery_codes(
    request: TwoFARegenerateCodesRequest,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> TwoFARegenerateCodesResponse:
    """
    Regenerates recovery codes after verifying the current TOTP code.
    Old codes are invalidated. New codes shown only once.
    """
    service = make_user_service(ahttp_client)
    totp_recovery_repo = TotpRecoveryCodesRepository(ahttp_client)
    codes = await service.regenerate_recovery_codes(
        current_user["id"], request.code, totp_recovery_repo
    )
    return TwoFARegenerateCodesResponse(recovery_codes=codes)


@router.post("/forgot-password", response_model=SetPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> SetPasswordResponse:
    """
    Initiates the forgot password flow.

    Sends a password reset link to the provided email if an active account
    exists. Always returns success to prevent email enumeration.
    """
    service = make_user_service(ahttp_client)
    estate_id = str(request.estate_id) if request.estate_id else None
    result = await service.forgot_password(request.email, estate_id)
    if result:
        email, first_name, token = result
        background_tasks.add_task(
            send_password_reset_email, email, first_name, token
        )

    return SetPasswordResponse(
        success=True,
        message=(
            "If an account with that email exists, "
            "a password reset link has been sent."
        ),
    )
