import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRY_MINUTES = 60 * 24  # 1 Day (customize as needed)
TWO_FA_PENDING_EXPIRE_MINUTES = 5


def generate_email_token(user_id: UUID) -> str:
    """
    Generates a JWT token for email verification.

    Args:
        user_id (UUID): ID of the user to encode.

    Returns:
        str: JWT token as a string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRY_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "scope": "email_verification",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_email_token(token: str) -> UUID:
    """
    Decodes and validates a JWT token for email verification.

    Args:
        token (str): Encoded JWT token.

    Returns:
        UUID: Extracted user ID from the token.

    Raises:
        jwt.PyJWTError: If decoding fails or token is expired.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("scope") != "email_verification":
        raise jwt.InvalidTokenError("Invalid token scope.")
    return UUID(payload["sub"])


def generate_password_reset_token(user_id: UUID) -> str:
    """
    Generates a JWT token for password reset.

    Args:
        user_id (UUID): ID of the user to encode.

    Returns:
        str: JWT token as a string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRY_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "scope": "password_reset",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> UUID:
    """
    Decodes and validates a JWT token for password reset.

    Args:
        token (str): Encoded JWT token.

    Returns:
        UUID: Extracted user ID from the token.

    Raises:
        jwt.PyJWTError: If decoding fails or token is expired.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("scope") != "password_reset":
        raise jwt.InvalidTokenError("Invalid token scope.")
    return UUID(payload["sub"])


def generate_tos_pending_token(user_id: UUID) -> str:
    """
    Generates a short-lived JWT token for users who must accept the TOS.
    This token is rejected by the auth middleware for all endpoints except
    POST /auth/accept-tos.

    Args:
        user_id (UUID): ID of the user to encode.

    Returns:
        str: JWT token as a string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRY_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "scope": "tos_pending",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_tos_pending_token(token: str) -> UUID:
    """
    Decodes and validates a TOS-pending JWT token.

    Args:
        token (str): Encoded JWT token.

    Returns:
        UUID: Extracted user ID from the token.

    Raises:
        jwt.PyJWTError: If decoding fails or token is expired.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("scope") != "tos_pending":
        raise jwt.InvalidTokenError("Invalid token scope.")
    return UUID(payload["sub"])


def generate_2fa_pending_token(user_id: UUID) -> str:
    """
    Generates a short-lived JWT token for users who must complete 2FA.
    This token is rejected by the auth middleware for all endpoints except
    POST /auth/2fa/verify and POST /auth/2fa/recover.

    Args:
        user_id (UUID): ID of the user to encode.

    Returns:
        str: JWT token as a string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TWO_FA_PENDING_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "scope": "2fa_pending",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_2fa_pending_token(token: str) -> UUID:
    """
    Decodes and validates a 2FA-pending JWT token.

    Args:
        token (str): Encoded JWT token.

    Returns:
        UUID: Extracted user ID from the token.

    Raises:
        jwt.PyJWTError: If decoding fails or token is expired.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("scope") != "2fa_pending":
        raise jwt.InvalidTokenError("Invalid token scope.")
    return UUID(payload["sub"])
