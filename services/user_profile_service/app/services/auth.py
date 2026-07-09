import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
from fastapi import HTTPException

from app.core.config import settings
from app.libs.notify import fire_notify
from app.repositories.session import SessionRepository
from app.repositories.totp_recovery_codes import TotpRecoveryCodesRepository
from gatepass_auth import get_current_user  # noqa: F401
from gatepass_auth import get_current_user_unverified  # noqa: F401

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = settings.LOGIN_EXPIRE_MINUTES


def generate_access_token(user: dict, session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "estate_id": user.get("estate_id"),
        "session_id": session_id,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class AuthService:
    """
    Service layer for all authentication and session flows.
    Endpoints delegate to this class; no repo calls in the API layer.
    """

    def __init__(
        self,
        user_service,  # UserService — imported lazily to avoid circular deps
        session_repo: SessionRepository,
        totp_recovery_repo: TotpRecoveryCodesRepository,
    ):
        self.user_service = user_service
        self.session_repo = session_repo
        self.totp_recovery_repo = totp_recovery_repo

    # ------------------------------------------------------------------
    # Login flows
    # ------------------------------------------------------------------

    async def login(
        self,
        email: str,
        password: str,
        estate_id: str | None,
        ip: str | None,
        device: str | None,
    ):
        from app.libs.auth_helpers import session_expires_at
        from app.services.token import (
            generate_2fa_pending_token,
            generate_tos_pending_token,
        )

        user = await self.user_service.repository.authenticate_user(
            email, password, estate_id
        )

        if user.get("role") != "root" and not estate_id:
            raise HTTPException(
                status_code=422,
                detail="estate_id is required for non-root login.",
            )

        if user.get("totp_enabled"):
            now = datetime.now(timezone.utc)
            familiar_cutoff = now - timedelta(
                days=settings.TWO_FA_FAMILIAR_IP_DAYS
            )
            force_reauth_cutoff = now - timedelta(
                days=settings.TWO_FA_FORCE_REAUTH_DAYS
            )

            familiar = await self.session_repo.search_sessions(
                user_id=str(user["id"]),
                ip_address=ip,
                is_2fa_verified=True,
                last_active_after=familiar_cutoff,
            )

            last_2fa_raw = user.get("last_2fa_verified_at")
            reauth_needed = not last_2fa_raw or (
                datetime.fromisoformat(last_2fa_raw) < force_reauth_cutoff
            )

            if not familiar.get("items") or reauth_needed:
                two_fa_token = generate_2fa_pending_token(user["id"])
                from app.schemas.auth import LoginResponse

                return LoginResponse(
                    success=True,
                    requires_2fa=True,
                    two_fa_token=two_fa_token,
                )

            session = await self.session_repo.create_session(
                user_id=str(user["id"]),
                ip_address=ip,
                device_name=device,
                expires_at=session_expires_at(),
                is_2fa_verified=True,
            )
        else:
            # Check whether this IP has been seen before for non-2FA users
            familiar_cutoff = datetime.now(timezone.utc) - timedelta(
                days=settings.TWO_FA_FAMILIAR_IP_DAYS
            )
            familiar = await self.session_repo.search_sessions(
                user_id=str(user["id"]),
                ip_address=ip,
                last_active_after=familiar_cutoff,
            )
            is_new_device = not familiar.get("items")

            session = await self.session_repo.create_session(
                user_id=str(user["id"]),
                ip_address=ip,
                device_name=device,
                expires_at=session_expires_at(),
                is_2fa_verified=False,
            )

            if is_new_device:
                asyncio.create_task(
                    fire_notify(
                        {
                            "type": "LOGIN_NEW_DEVICE",
                            "title": "New device login",
                            "body": (
                                "Your account was accessed from a "
                                "new device or location."
                            ),
                            "recipient_user_ids": [str(user["id"])],
                            "metadata": {
                                "ip_address": ip or "",
                                "device_name": device,
                                "session_id": session.get("id", ""),
                            },
                        }
                    )
                )

        from app.schemas.auth import LoginResponse

        if user.get("tos_accepted_version") != settings.TOS_VERSION:
            tos_token = generate_tos_pending_token(user["id"])
            return LoginResponse(
                success=True,
                role=user["role"],
                access_token=tos_token,
                requires_tos_acceptance=True,
            )

        token = generate_access_token(user, session["id"])
        return LoginResponse(
            success=True,
            role=user["role"],
            access_token=token,
            session_id=session["id"],
        )

    async def verify_2fa(
        self,
        two_fa_token: str,
        code: str,
        ip: str | None,
        device: str | None,
    ):
        from app.libs.auth_helpers import session_expires_at
        from app.schemas.auth import LoginResponse
        from app.services.token import (
            decode_2fa_pending_token,
            generate_tos_pending_token,
        )

        try:
            user_id = decode_2fa_pending_token(two_fa_token)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid or expired 2FA token."
            )

        user = await self.user_service.repository.get_user_by_id(str(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        if not await self.user_service.verify_totp_code(str(user_id), code):
            raise HTTPException(status_code=401, detail="Invalid TOTP code.")

        now = datetime.now(timezone.utc)
        await self.user_service.repository.client.async_patch(
            f"{self.user_service.repository.users_endpoint}/{user_id}",
            json_data={"last_2fa_verified_at": now.isoformat()},
        )

        session = await self.session_repo.create_session(
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
            success=True,
            role=user_dict["role"],
            access_token=token,
            session_id=session["id"],
        )

    async def recover_2fa(
        self,
        two_fa_token: str,
        recovery_code: str,
        ip: str | None,
        device: str | None,
    ):
        from app.libs.auth_helpers import session_expires_at
        from app.schemas.auth import LoginResponse
        from app.services.token import generate_tos_pending_token

        user_dict = await self.user_service.recover_with_code(
            two_fa_token, recovery_code, self.totp_recovery_repo
        )

        now = datetime.now(timezone.utc)
        await self.user_service.repository.client.async_patch(
            f"{self.user_service.repository.users_endpoint}"
            f"/{user_dict['id']}",
            json_data={"last_2fa_verified_at": now.isoformat()},
        )

        session = await self.session_repo.create_session(
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
            success=True,
            role=user_dict["role"],
            access_token=token,
            session_id=session["id"],
        )

    async def accept_tos(
        self,
        tos_token: str,
        ip: str | None,
        device: str | None,
    ):
        from app.libs.auth_helpers import session_expires_at
        from app.schemas.auth import LoginResponse

        user = await self.user_service.accept_tos(tos_token)

        session = await self.session_repo.create_session(
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
            session_id=session["id"],
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def logout(self, session_id: str) -> dict:
        await self.session_repo.delete_session(session_id)
        return {"success": True, "message": "Logged out successfully."}

    async def list_sessions(self, user_id: str):
        from app.schemas.auth import SessionListResponse, SessionResponse

        result = await self.session_repo.search_sessions(
            user_id=user_id, limit=100
        )
        now = datetime.now(timezone.utc)
        items: List[SessionResponse] = [
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
            if datetime.fromisoformat(s["expires_at"]).replace(
                tzinfo=timezone.utc
            )
            > now
        ]
        return SessionListResponse(items=items, total=len(items))

    async def revoke_session(self, session_id: str, user_id: str) -> dict:
        session = await self.session_repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        if str(session.get("user_id")) != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only revoke your own sessions.",
            )
        await self.session_repo.delete_session(session_id)
        return {"success": True}

    async def revoke_all_sessions(self, user_id: str) -> dict:
        await self.session_repo.delete_all_sessions_for_user(user_id)
        return {"success": True, "message": "All sessions revoked."}

    # ------------------------------------------------------------------
    # 2FA management (delegates to UserService)
    # ------------------------------------------------------------------

    async def setup_2fa(self, user_id: str):
        from app.schemas.auth import TwoFASetupResponse

        result = await self.user_service.setup_2fa(user_id)
        return TwoFASetupResponse(**result)

    async def enable_2fa(self, user_id: str, code: str):
        from app.schemas.auth import TwoFAEnableResponse

        codes = await self.user_service.enable_2fa(
            user_id, code, self.totp_recovery_repo
        )
        return TwoFAEnableResponse(recovery_codes=codes)

    async def disable_2fa(self, user_id: str, code: str) -> None:
        await self.user_service.disable_2fa(
            user_id, code, self.totp_recovery_repo
        )

    async def regenerate_recovery_codes(self, user_id: str, code: str):
        from app.schemas.auth import TwoFARegenerateCodesResponse

        codes = await self.user_service.regenerate_recovery_codes(
            user_id, code, self.totp_recovery_repo
        )
        return TwoFARegenerateCodesResponse(recovery_codes=codes)
