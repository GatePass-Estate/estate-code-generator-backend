import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRY_MINUTES = 60 * 24 * 7  # 1 day (customize as needed)


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
