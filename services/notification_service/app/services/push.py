import json
import logging
from typing import Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings

logger = logging.getLogger(__name__)

_app: Optional[firebase_admin.App] = None


def _get_app() -> Optional[firebase_admin.App]:
    global _app
    if _app is not None:
        return _app
    if not settings.FCM_CREDENTIALS_JSON:
        logger.warning(
            "FCM_CREDENTIALS_JSON not set — push notifications disabled"
        )
        return None
    try:
        cred_dict = json.loads(settings.FCM_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
        _app = firebase_admin.initialize_app(cred)
        return _app
    except Exception:
        logger.exception("Failed to initialize Firebase app")
        return None


async def send_push(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Send a FCM multicast push notification to a list of device tokens.

    Data values must all be strings for FCM compatibility.

    Returns a list of tokens that FCM reported as unregistered so the
    caller can remove them from the database.
    """
    if not tokens:
        return []
    app = _get_app()
    if app is None:
        logger.warning(
            "FCM not initialised — skipping push for %d token(s)", len(tokens)
        )
        return []

    str_data = {k: str(v) for k, v in (data or {}).items()}

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=str_data,
        tokens=tokens,
    )
    stale_tokens: List[str] = []
    try:
        response = messaging.send_each_for_multicast(message, app=app)
        logger.info(
            "FCM multicast: %d success, %d failure",
            response.success_count,
            response.failure_count,
        )
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                logger.warning(
                    "FCM send failed for token[%d]: %s", idx, resp.exception
                )
                if isinstance(resp.exception, messaging.UnregisteredError):
                    stale_tokens.append(tokens[idx])
    except Exception:
        logger.exception("FCM multicast send raised an exception")
    return stale_tokens
