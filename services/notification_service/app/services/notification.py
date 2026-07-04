import logging
from typing import Any, Dict, List, Optional

from app.libs.http_handler import AsyncHttpHandler
from app.repositories.device_token import DeviceTokenRepository
from app.repositories.notification import NotificationRepository
from app.repositories.preference import PreferenceRepository
from app.repositories.user import UserRepository
from app.schemas.internal import FanOutSpec, InternalNotifyRequest
from app.schemas.notification import (
    EMAIL_TYPES,
    MANDATORY_TYPES,
    NO_IN_APP_TYPES,
    PUSH_TYPES,
    NotificationType,
)
from app.services.email import dispatch_email
from app.services.push import send_push

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrates notification fan-out: DB rows, push, and email."""

    def __init__(self, http_client: AsyncHttpHandler):
        self.notification_repo = NotificationRepository(http_client)
        self.device_token_repo = DeviceTokenRepository(http_client)
        self.preference_repo = PreferenceRepository(http_client)
        self.user_repo = UserRepository(http_client)

    # ── Recipient resolution ───────────────────────────────────────────────

    async def _resolve_recipients(
        self, request: InternalNotifyRequest
    ) -> List[str]:
        """Return a list of user ID strings to notify."""
        if request.recipient_user_ids:
            return [str(uid) for uid in request.recipient_user_ids]

        spec: FanOutSpec = request.fan_out  # type: ignore[assignment]
        estate_id = str(spec.estate_id)
        user_ids: List[str] = []

        for role in spec.roles:
            result = await self.user_repo.search(
                estate_id=estate_id, role=role
            )
            if not result:
                continue
            items = result.get("items") or result.get("data") or []
            for user in items:
                uid = user.get("id") or user.get("user_id")
                if uid and uid not in user_ids:
                    user_ids.append(uid)

        return user_ids

    # ── Preference helpers ─────────────────────────────────────────────────

    async def _get_prefs_map(self, user_id: str) -> Dict[str, Dict[str, bool]]:
        """Return {notification_type_value: {push_enabled, email_enabled}}."""
        result = await self.preference_repo.get_by_user(user_id)
        if not result:
            return {}
        items = result.get("items") or result.get("data") or []
        prefs: Dict[str, Dict[str, bool]] = {}
        for pref in items:
            t = pref.get("notification_type") or pref.get("type")
            if t:
                prefs[t] = {
                    "push_enabled": pref.get("push_enabled", True),
                    "email_enabled": pref.get("email_enabled", True),
                }
        return prefs

    def _push_allowed(
        self,
        notification_type: NotificationType,
        prefs: Dict[str, Dict[str, bool]],
    ) -> bool:
        if notification_type not in PUSH_TYPES:
            return False
        if notification_type in MANDATORY_TYPES:
            return True
        user_pref = prefs.get(notification_type.value)
        if user_pref is None:
            return True  # default on
        return user_pref.get("push_enabled", True)

    def _email_allowed(
        self,
        notification_type: NotificationType,
        prefs: Dict[str, Dict[str, bool]],
    ) -> bool:
        if notification_type not in EMAIL_TYPES:
            return False
        if notification_type in MANDATORY_TYPES:
            return True
        user_pref = prefs.get(notification_type.value)
        if user_pref is None:
            return True  # default on
        return user_pref.get("email_enabled", True)

    # ── Delivery per user ─────────────────────────────────────────────────

    async def _deliver_to_user(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        metadata: Optional[Dict[str, Any]],
        notification_id: Optional[str] = None,
    ) -> None:
        prefs = await self._get_prefs_map(user_id)

        if self._push_allowed(notification_type, prefs):
            token_result = await self.device_token_repo.get_by_user(user_id)
            tokens: List[str] = []
            if token_result:
                items = (
                    token_result.get("items") or token_result.get("data") or []
                )
                tokens = [t["token"] for t in items if t.get("token")]
            if tokens:
                fcm_data: Dict[str, str] = {"type": notification_type.value}
                if notification_id:
                    fcm_data["notification_id"] = notification_id
                if metadata:
                    fcm_data.update({k: str(v) for k, v in metadata.items()})
                stale = await send_push(
                    tokens=tokens,
                    title=title,
                    body=body,
                    data=fcm_data,
                )
                for stale_token in stale:
                    try:
                        await self.device_token_repo.remove_by_token(
                            stale_token
                        )
                        logger.info("Removed stale FCM token: %s", stale_token)
                    except Exception:
                        logger.warning(
                            "Failed to remove stale FCM token: %s", stale_token
                        )

        if self._email_allowed(notification_type, prefs):
            user = await self.user_repo.get(user_id)
            if user:
                email = user.get("email")
                first_name = user.get("first_name") or user.get("firstname")
                if email:
                    try:
                        await dispatch_email(
                            notification_type=notification_type,
                            email=email,
                            first_name=first_name or "",
                            metadata=metadata or {},
                        )
                    except Exception:
                        logger.exception(
                            "Email dispatch failed for user %s type %s",
                            user_id,
                            notification_type.value,
                        )

    # ── Main entry point ──────────────────────────────────────────────────

    async def process(self, request: InternalNotifyRequest) -> None:
        """
        Resolve recipients, persist notification rows, then deliver
        push and email per-user.
        """
        user_ids = await self._resolve_recipients(request)
        if not user_ids:
            logger.warning(
                "No recipients resolved for notification type %s",
                request.type.value,
            )
            return

        # Persist in-app rows (skipped for email-only transactional types)
        # Build a user_id → notification_id map so the ID can be forwarded
        # in the FCM data payload for client-side deep-linking / mark-as-read.
        notification_id_by_user: Dict[str, str] = {}
        if request.type not in NO_IN_APP_TYPES:
            rows = [
                {
                    "user_id": uid,
                    "type": request.type.value,
                    "title": request.title,
                    "body": request.body,
                    "payload": request.metadata,
                }
                for uid in user_ids
            ]
            created = await self.notification_repo.create_bulk(rows)
            if created:
                for row in created:
                    uid = row.get("user_id")
                    nid = row.get("id")
                    if uid and nid:
                        notification_id_by_user[str(uid)] = str(nid)

        # Deliver to each recipient
        for user_id in user_ids:
            try:
                await self._deliver_to_user(
                    user_id=user_id,
                    notification_type=request.type,
                    title=request.title,
                    body=request.body,
                    metadata=request.metadata,
                    notification_id=notification_id_by_user.get(user_id),
                )
            except Exception:
                logger.exception(
                    "Delivery failed for user %s type %s",
                    user_id,
                    request.type.value,
                )
