"""Checkout session token — short-lived JWT for polling the status endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

_ALGORITHM = "HS256"
_SCOPE = "checkout"


def generate_checkout_token(checkout_session_id: str, secret_key: str) -> str:
    """
    Mint a short-lived JWT scoped to a single checkout session.

    Args:
        checkout_session_id: The session UUID to embed as the subject.
        secret_key: HMAC signing key (settings.SECRET_KEY).

    Returns:
        Signed JWT string.
    """
    payload = {
        "sub": checkout_session_id,
        "scope": _SCOPE,
        "exp": datetime.now(tz=timezone.utc)
        + timedelta(seconds=settings.CHECKOUT_TOKEN_EXPIRY_SECONDS),
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def verify_checkout_token(token: str, secret_key: str) -> str | None:
    """
    Decode and validate a checkout token.

    Args:
        token: JWT string from the Authorization header.
        secret_key: HMAC signing key (settings.SECRET_KEY).

    Returns:
        The checkout_session_id (sub) if the token is valid and scoped
        correctly, or None if invalid, expired, or wrong scope.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        if payload.get("scope") != _SCOPE:
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
