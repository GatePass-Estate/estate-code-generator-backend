import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
from fastapi import HTTPException

from app.core.config import settings
from app.libs.auth_helpers import session_expires_at
from app.libs.notify import fire_notify
from app.repositories.session import SessionRepository
from app.repositories.totp_recovery_codes import TotpRecoveryCodesRepository
from app.repositories.trusted_device import TrustedDeviceRepository
from app.schemas.auth import (
    BiometricEnableResponse,
    BiometricLoginResponse,
    LoginResponse,
    SessionListResponse,
    SessionResponse,
    TwoFAEnableResponse,
    TwoFARegenerateCodesResponse,
    TwoFASetupResponse,
)
from gatepass_auth import auth_token_from_request  # noqa: F401
from gatepass_auth import get_current_user  # noqa: F401
from gatepass_auth import get_current_user_unverified  # noqa: F401

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_MINUTES = settings.REFRESH_TOKEN_EXPIRE_MINUTES


def _generate_biometric_token() -> tuple[str, str]:
    """Return (plaintext_token, sha256_hex_hash).

    The plaintext is given to the FE once and stored in SecureStore.
    Only the hash is persisted on the backend.
    """
    token = secrets.token_urlsafe(32)
    hash_ = hashlib.sha256(token.encode()).hexdigest()
    return token, hash_


def _generate_device_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash)."""
    token = secrets.token_urlsafe(64)
    hash_ = hashlib.sha256(token.encode()).hexdigest()
    return token, hash_


def generate_access_token(user: dict, session_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
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


def generate_refresh_token(session_id: str) -> tuple[str, str]:
    """Return (refresh_jwt, jti_hash).

    The JWT is returned to the client.  Only the SHA-256 hash of the
    jti is stored on the session row so we can validate on refresh and
    detect reuse.
    """
    jti = secrets.token_urlsafe(32)
    jti_hash = hashlib.sha256(jti.encode()).hexdigest()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=REFRESH_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "session_id": session_id,
        "scope": "refresh",
        "jti": jti,
        "exp": expire,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti_hash


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
        trusted_device_repo: TrustedDeviceRepository,
    ):
        self.user_service = user_service
        self.session_repo = session_repo
        self.totp_recovery_repo = totp_recovery_repo
        self.trusted_device_repo = trusted_device_repo

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    async def _issue_token_pair(
        self, user: dict, session_id: str
    ) -> tuple[str, str]:
        """Issue access + refresh tokens and persist the refresh hash."""
        access_token = generate_access_token(user, session_id)
        refresh_token, jti_hash = generate_refresh_token(session_id)
        await self.session_repo.update_session(
            session_id, {"refresh_token_hash": jti_hash}
        )
        return access_token, refresh_token

    # ------------------------------------------------------------------
    # Device trust helpers
    # ------------------------------------------------------------------

    async def _check_device_trust(
        self, user_id: str, device_token_raw: str | None
    ) -> dict | None:
        """Hash the token and look up trusted_devices.

        Returns the device row dict or None.
        """
        if not device_token_raw:
            return None
        token_hash = hashlib.sha256(device_token_raw.encode()).hexdigest()
        device = await self.trusted_device_repo.get_by_token_hash(token_hash)
        if not device:
            return None
        if device.get("is_revoked") or device.get("is_deleted"):
            return None
        expires_at = datetime.fromisoformat(device["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return None
        if str(device.get("user_id")) != user_id:
            return None
        return device

    async def _issue_device_token(
        self, user_id: str, ip: str | None, device_label: str | None
    ) -> tuple[str, str]:
        """Create trusted_devices row, return (raw_token, device_id)."""
        raw_token, token_hash = _generate_device_token()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.TRUSTED_DEVICE_EXPIRY_DAYS)
        result = await self.trusted_device_repo.create_device(
            user_id=user_id,
            token_hash=token_hash,
            device_label=device_label,
            ip_address=ip,
            last_seen_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
        )
        return raw_token, result["id"]

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
        device_token_raw: str | None = None,
    ):
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

        if estate_id:
            try:
                estate = await (
                    self.user_service.estate_repository.get_estate_by_id(
                        estate_id
                    )
                )
            except HTTPException:
                raise HTTPException(
                    status_code=403, detail="Estate not found."
                )
            if not estate.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="This estate has been deactivated.",
                )

        # Check device trust (replaces IP familiarity)
        trusted_device = await self._check_device_trust(
            str(user["id"]), device_token_raw
        )

        if user.get("totp_enabled"):
            now = datetime.now(timezone.utc)
            force_reauth_cutoff = now - timedelta(
                days=settings.TWO_FA_FORCE_REAUTH_DAYS
            )

            last_2fa_raw = user.get("last_2fa_verified_at")
            reauth_needed = not last_2fa_raw or (
                datetime.fromisoformat(last_2fa_raw) < force_reauth_cutoff
            )

            if not trusted_device or reauth_needed:
                # New device or force-reauth — require 2FA
                # Send notification now so user is warned even if
                # the attacker can't complete 2FA.  Wording says
                # "attempt" because 2FA hasn't been passed yet.
                asyncio.create_task(
                    fire_notify(
                        {
                            "type": "LOGIN_NEW_DEVICE",
                            "title": "Login attempt",
                            "body": (
                                "A login attempt was made on your "
                                "account from a new device."
                            ),
                            "recipient_user_ids": [str(user["id"])],
                            "metadata": {
                                "ip_address": ip or "",
                                "device_name": device,
                                "is_2fa_pending": True,
                            },
                        }
                    )
                )
                two_fa_token = generate_2fa_pending_token(user["id"])
                return LoginResponse(
                    success=True,
                    requires_2fa=True,
                    two_fa_token=two_fa_token,
                )

            is_2fa_verified = True
            is_new_device = False
        else:
            is_new_device = not trusted_device
            is_2fa_verified = False

        # Check TOS BEFORE creating a session to avoid orphaned sessions.
        if user.get("tos_accepted_version") != settings.TOS_VERSION:
            tos_token = generate_tos_pending_token(user["id"])
            return LoginResponse(
                success=True,
                role=user["role"],
                access_token=tos_token,
                requires_tos_acceptance=True,
            )

        # Link trusted device or issue new one
        device_token_response = None
        trusted_device_id = None
        if trusted_device:
            trusted_device_id = trusted_device["id"]
            # Update last_seen_at
            await self.trusted_device_repo.update_device(
                trusted_device_id,
                {"last_seen_at": datetime.now(timezone.utc).isoformat()},
            )
        elif is_new_device:
            raw_token, new_device_id = await self._issue_device_token(
                str(user["id"]), ip, device
            )
            trusted_device_id = new_device_id
            device_token_response = raw_token

        session = await self.session_repo.create_session(
            user_id=str(user["id"]),
            ip_address=ip,
            device_name=device,
            expires_at=session_expires_at(),
            is_2fa_verified=is_2fa_verified,
            trusted_device_id=trusted_device_id,
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

        access_token, refresh_token = await self._issue_token_pair(
            user, session["id"]
        )
        return LoginResponse(
            success=True,
            role=user["role"],
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session["id"],
            device_token=device_token_response,
        )

    async def verify_2fa(
        self,
        two_fa_token: str,
        code: str,
        ip: str | None,
        device: str | None,
    ):
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

        # Device is always new when 2FA was prompted — issue fresh token
        raw_token, new_device_id = await self._issue_device_token(
            str(user_id), ip, device
        )

        session = await self.session_repo.create_session(
            user_id=str(user_id),
            ip_address=ip,
            device_name=device,
            expires_at=session_expires_at(),
            is_2fa_verified=True,
            trusted_device_id=new_device_id,
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
                device_token=raw_token,
            )

        access_token, refresh_token = await self._issue_token_pair(
            user_dict, session["id"]
        )
        return LoginResponse(
            success=True,
            role=user_dict["role"],
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session["id"],
            device_token=raw_token,
        )

    async def recover_2fa(
        self,
        two_fa_token: str,
        recovery_code: str,
        ip: str | None,
        device: str | None,
    ):
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

        # Recovery code use is a revocation trigger
        await self.trusted_device_repo.revoke_all_for_user(user_dict["id"])

        # Issue fresh device token
        raw_token, new_device_id = await self._issue_device_token(
            user_dict["id"], ip, device
        )

        session = await self.session_repo.create_session(
            user_id=user_dict["id"],
            ip_address=ip,
            device_name=device,
            expires_at=session_expires_at(),
            is_2fa_verified=True,
            trusted_device_id=new_device_id,
        )

        if user_dict.get("tos_accepted_version") != settings.TOS_VERSION:
            tos_token = generate_tos_pending_token(user_dict["id"])
            return LoginResponse(
                success=True,
                role=user_dict["role"],
                access_token=tos_token,
                requires_tos_acceptance=True,
                device_token=raw_token,
            )

        access_token, refresh_token = await self._issue_token_pair(
            user_dict, session["id"]
        )
        return LoginResponse(
            success=True,
            role=user_dict["role"],
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session["id"],
            device_token=raw_token,
        )

    async def accept_tos(
        self,
        tos_token: str,
        ip: str | None,
        device: str | None,
        device_token_raw: str | None = None,
    ):
        user = await self.user_service.accept_tos(tos_token)

        # Re-check device trust
        trusted_device = await self._check_device_trust(
            user["id"], device_token_raw
        )

        device_token_response = None
        trusted_device_id = None
        if trusted_device:
            trusted_device_id = trusted_device["id"]
        else:
            # New device — issue token
            raw_token, new_device_id = await self._issue_device_token(
                user["id"], ip, device
            )
            trusted_device_id = new_device_id
            device_token_response = raw_token

        session = await self.session_repo.create_session(
            user_id=user["id"],
            ip_address=ip,
            device_name=device,
            expires_at=session_expires_at(),
            is_2fa_verified=user.get("totp_enabled", False),
            trusted_device_id=trusted_device_id,
        )

        access_token, refresh_token = await self._issue_token_pair(
            user, session["id"]
        )
        return LoginResponse(
            success=True,
            role=user["role"],
            access_token=access_token,
            refresh_token=refresh_token,
            requires_tos_acceptance=False,
            session_id=session["id"],
            device_token=device_token_response,
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def logout(self, session_id: str) -> dict:
        await self.session_repo.delete_session(session_id)
        return {"success": True, "message": "Logged out successfully."}

    async def list_sessions(self, user_id: str):
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
    # Token refresh
    # ------------------------------------------------------------------

    async def refresh_tokens(self, refresh_token_jwt: str):
        """
        Exchange a valid refresh token for a new access + refresh pair.

        Validates the refresh JWT, checks the jti hash against the
        stored hash on the session, and rotates the token.  If the
        hash does not match, the session is revoked (theft detection).
        """
        try:
            payload = jwt.decode(
                refresh_token_jwt,
                SECRET_KEY,
                algorithms=[ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Refresh token has expired.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token.",
            )

        if payload.get("scope") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token scope.",
            )

        session_id = payload.get("session_id")
        jti = payload.get("jti")
        if not session_id or not jti:
            raise HTTPException(
                status_code=401,
                detail="Malformed refresh token.",
            )

        # Validate session + user + estate and get hash in one call.
        data = await self.session_repo.validate_session(session_id)
        if not data:
            raise HTTPException(
                status_code=401,
                detail="Session is invalid or expired.",
            )

        presented_hash = hashlib.sha256(jti.encode()).hexdigest()
        stored_hash = data.get("refresh_token_hash")
        if presented_hash != stored_hash:
            await self.session_repo.delete_session(session_id)
            raise HTTPException(
                status_code=401,
                detail=(
                    "Refresh token reuse detected. "
                    "Session revoked for security."
                ),
            )

        user_dict = {
            "id": str(data["user_id"]),
            "email": data["email"],
            "role": data["role"],
            "estate_id": (
                str(data["estate_id"]) if data.get("estate_id") else None
            ),
        }

        access_token, refresh_token = await self._issue_token_pair(
            user_dict, session_id
        )
        return LoginResponse(
            success=True,
            role=user_dict["role"],
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # 2FA management (delegates to UserService)
    # ------------------------------------------------------------------

    async def setup_2fa(self, user_id: str):
        result = await self.user_service.setup_2fa(user_id)
        return TwoFASetupResponse(**result)

    async def enable_2fa(
        self,
        user_id: str,
        code: str,
        ip: str | None = None,
        device_label: str | None = None,
    ):
        codes = await self.user_service.enable_2fa(
            user_id, code, self.totp_recovery_repo
        )
        # Revoke all existing trusted devices — tokens issued without 2FA
        # should not skip 2FA after the user turns it on.
        await self.trusted_device_repo.revoke_all_for_user(user_id)
        # Issue fresh device token for current device
        raw_token, _ = await self._issue_device_token(
            user_id, ip, device_label
        )
        return TwoFAEnableResponse(
            recovery_codes=codes, device_token=raw_token
        )

    async def disable_2fa(self, user_id: str, code: str) -> None:
        await self.user_service.disable_2fa(
            user_id, code, self.totp_recovery_repo
        )

    async def regenerate_recovery_codes(self, user_id: str, code: str):
        codes = await self.user_service.regenerate_recovery_codes(
            user_id, code, self.totp_recovery_repo
        )
        return TwoFARegenerateCodesResponse(recovery_codes=codes)

    # ------------------------------------------------------------------
    # Biometric login
    # ------------------------------------------------------------------

    async def enable_biometric(self, session_id: str):
        """
        Issue a biometric token tied to the current session.

        Generates a random token, stores its SHA-256 hash on the session
        row, and returns the plaintext token to the caller (FE stores it
        in SecureStore behind Face ID / fingerprint).

        Args:
            session_id: The caller's current session ID (from JWT).

        Returns:
            BiometricEnableResponse with plaintext biometric_token.
        """

        token, hash_ = _generate_biometric_token()
        await self.session_repo.enable_biometric(session_id, hash_)
        return BiometricEnableResponse(biometric_token=token)

    async def biometric_login(
        self,
        biometric_token: str,
        estate_id: str,
        ip: str | None,
        device: str | None,
        device_token_raw: str | None = None,
    ):
        """
        Exchange a biometric token for a fresh 1-hour access JWT.

        Flow:
        1. Hash the token and look up the session.
        2. Validate session is not expired.
        3. Fetch the user; confirm estate matches.
        4. If 2FA force-reauth is due, clear the token and signal FE.
        5. Rotate the biometric token and extend session expiry.
        6. Check / refresh device trust token.
        7. Issue a new access token against the same session.
        """

        token_hash = hashlib.sha256(biometric_token.encode()).hexdigest()

        session = await self.session_repo.get_session_by_biometric_hash(
            token_hash
        )
        if not session:
            raise HTTPException(
                status_code=401, detail="Invalid or expired biometric token."
            )

        now = datetime.now(timezone.utc)
        expires_at_str = session.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                raise HTTPException(
                    status_code=401, detail="Biometric session has expired."
                )

        user = await self.user_service.repository.get_user_by_id(
            session["user_id"]
        )
        if not user or not user.status or user.is_deleted:
            raise HTTPException(
                status_code=401, detail="User not found or inactive."
            )

        if str(user.estate_id) != estate_id:
            raise HTTPException(
                status_code=401,
                detail="Biometric token does not match this estate.",
            )

        if user.totp_enabled:
            force_reauth_cutoff = now - timedelta(
                days=settings.TWO_FA_FORCE_REAUTH_DAYS
            )
            last_2fa_raw = user.last_2fa_verified_at
            reauth_needed = not last_2fa_raw or (
                datetime.fromisoformat(str(last_2fa_raw)) < force_reauth_cutoff
            )
            if reauth_needed:
                await self.session_repo.disable_biometric(session["id"])
                return BiometricLoginResponse(
                    success=False,
                    requires_full_reauth=True,
                )

        new_token, new_hash = _generate_biometric_token()
        await self.session_repo.rotate_biometric_token(
            session["id"], new_hash, session_expires_at()
        )

        # Handle device trust
        trusted_device = await self._check_device_trust(
            str(user.id), device_token_raw
        )
        device_token_response = None
        if trusted_device:
            await self.trusted_device_repo.update_device(
                trusted_device["id"],
                {"last_seen_at": now.isoformat()},
            )
        else:
            # Biometric = device proof, issue fresh token silently
            raw_token, _ = await self._issue_device_token(
                str(user.id), ip, device
            )
            device_token_response = raw_token

        user_dict = {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "estate_id": str(user.estate_id) if user.estate_id else None,
        }
        access_token, refresh_token = await self._issue_token_pair(
            user_dict, session["id"]
        )

        return BiometricLoginResponse(
            success=True,
            role=user.role,
            access_token=access_token,
            refresh_token=refresh_token,
            session_id=session["id"],
            biometric_token=new_token,
            device_token=device_token_response,
        )

    async def disable_biometric(self, session_id: str) -> dict:
        """
        Remove the biometric token from the current session.

        After this call the FE should clear the token from SecureStore.

        Args:
            session_id: The caller's current session ID (from JWT).

        Returns:
            Success dict.
        """
        await self.session_repo.disable_biometric(session_id)
        return {"success": True}
